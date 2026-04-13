import traceback
import logging
import os
import subprocess
import zipfile
import shutil
import tempfile
from datetime import timedelta
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncHour
from severynsor.models import Sensor, SensorRetriever, ValueSensor, ImageSensor, ValueRecord, ImageRecord
from severynsor.models.log import ActivityLog

logger = logging.getLogger(__name__)

def _send_task_email(user_email, task_name, success, details=""):
    subject = f"{'💎' if success else '⚠️'} Severynsor Task: {task_name}"
    
    # Context for the template
    domain = getattr(settings, 'SITE_DOMAIN', 'localhost:8000')
    schema = "https" if not settings.DEBUG else "http"
    summary_url = f"{schema}://{domain}" + reverse('system_view')
    
    context = {
        'task_name': task_name,
        'success': success,
        'details': details,
        'timestamp': timezone.now(),
        'summary_url': summary_url,
    }

    try:
        html_content = render_to_string('emails/task_notification.html', context)
        text_content = strip_tags(html_content)
        
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()
    except Exception as e:
        logger.error(f"Failed to send task email: {e}")

def grab_data_task(retriever_id):
    """
    Task to execute a single retriever's grab_data method.
    """
    try:
        retriever = SensorRetriever.objects.get(pk=retriever_id)
    except SensorRetriever.DoesNotExist:
        logger.error(f"Retriever {retriever_id} does not exist.")
        return

    start_time = timezone.now()
    try:
        logger.info(f"Running task for retriever {retriever}")
        retriever.grab_data()
        
        ActivityLog.objects.create(
            type=ActivityLog.RETRIEVER,
            sensor=retriever.sensor,
            retriever=retriever,
            success=True,
            timestamp=start_time,
            duration=(timezone.now() - start_time).total_seconds()
        )
        return True
    except NotImplementedError:
        error_msg = f"Retriever {retriever} has not implemented grab_data()."
        logger.warning(error_msg)
        ActivityLog.objects.create(
            type=ActivityLog.RETRIEVER,
            sensor=retriever.sensor,
            retriever=retriever,
            success=False,
            error_message=error_msg,
            timestamp=start_time,
            duration=(timezone.now() - start_time).total_seconds()
        )
        return False
    except Exception as e:
        error_msg = f"Error running retriever {retriever}: {e}"
        logger.error(error_msg)
        ActivityLog.objects.create(
            type=ActivityLog.RETRIEVER,
            sensor=retriever.sensor,
            retriever=retriever,
            success=False,
            error_message=f"{str(e)}\n{traceback.format_exc()}",
            timestamp=start_time,
            duration=(timezone.now() - start_time).total_seconds()
        )
        return False

def cleanup_value_logs(user_email):
    """
    Minimize value logs: keep only border values for each identical sequence in 1h buckets.
    """
    try:
        sensors = ValueSensor.objects.all()
        deleted_count = 0
        for sensor in sensors:
            # Group by hour to manage performance
            hour_buckets = ValueRecord.objects.filter(sensor=sensor).annotate(hour=TruncHour('timestamp')).values('hour').distinct()
            
            for bucket in hour_buckets:
                # Get records for this specific hour
                h_start = bucket['hour']
                h_end = h_start + timedelta(hours=1)
                records = list(ValueRecord.objects.filter(sensor=sensor, timestamp__gte=h_start, timestamp__lt=h_end).order_by('timestamp'))
                
                if len(records) < 3:
                    continue
                
                to_delete = []
                for i in range(1, len(records) - 1):
                    # Check if middle record can be deleted
                    # If it's the same value as previous and next, it's redundant (border values preserved)
                    if records[i].value == records[i-1].value and records[i].value == records[i+1].value:
                        to_delete.append(records[i].id)
                
                if to_delete:
                    with transaction.atomic():
                        _, deleted = ValueRecord.objects.filter(id__in=to_delete).delete()
                        deleted_count += deleted

        _send_task_email(user_email, "Minimize Value Logs", True, f"Operation successful. Deleted {deleted_count} redundant records.")
    except Exception as e:
        logger.error(f"Cleanup value logs failed: {e}")
        _send_task_email(user_email, "Minimize Value Logs", False, str(e))

def cleanup_image_logs(user_email):
    """
    For images older than 1 month, leave only one per hour.
    """
    try:
        one_month_ago = timezone.now() - timedelta(days=30)
        sensors = ImageSensor.objects.all()
        deleted_count = 0
        
        for sensor in sensors:
            # Find hours that have more than 1 record
            duplicate_hours = (
                ImageRecord.objects.filter(sensor=sensor, timestamp__lt=one_month_ago)
                .annotate(hour=TruncHour('timestamp'))
                .values('hour')
                .annotate(count=Count('id'))
                .filter(count__gt=1)
            )
            
            for entry in duplicate_hours:
                hour_start = entry['hour']
                hour_end = hour_start + timedelta(hours=1)
                
                # Get all records in this hour, keep the first one
                records = list(ImageRecord.objects.filter(sensor=sensor, timestamp__gte=hour_start, timestamp__lt=hour_end).order_by('timestamp').values_list('id', flat=True))
                
                if len(records) > 1:
                    to_delete = records[1:]
                    _, deleted = ImageRecord.objects.filter(id__in=to_delete).delete()
                    deleted_count += deleted
        
        _send_task_email(user_email, "Compress Image Logs (>1mo)", True, f"Operation successful. Deleted {deleted_count} redundant image records.")
    except Exception as e:
        logger.error(f"Cleanup image logs failed: {e}")
        _send_task_email(user_email, "Compress Image Logs (>1mo)", False, str(e))

def remove_old_value_entries(user_email):
    """
    Remove value entries older than 1 year.
    """
    try:
        one_year_ago = timezone.now() - timedelta(days=365)
        _, deleted = ValueRecord.objects.filter(timestamp__lt=one_year_ago).delete()
        _send_task_email(user_email, "Remove Old Value Entries (>1y)", True, f"Deleted {deleted} records.")
    except Exception as e:
        _send_task_email(user_email, "Remove Old Value Entries (>1y)", False, str(e))

def remove_old_image_entries(user_email):
    """
    Remove image entries older than 1 year.
    """
    try:
        one_year_ago = timezone.now() - timedelta(days=365)
        _, deleted = ImageRecord.objects.filter(timestamp__lt=one_year_ago).delete()
        _send_task_email(user_email, "Remove Old Image Entries (>1y)", True, f"Deleted {deleted} records.")
    except Exception as e:
        _send_task_email(user_email, "Remove Old Image Entries (>1y)", False, str(e))

def cleanup_backups_task(user_email):
    """
    Remove all backups except the latest one.
    """
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            _send_task_email(user_email, "Cleanup Backups", True, "Backup directory does not exist. Nothing to cleanup.")
            return

        backups = [f for f in os.listdir(backup_dir) if f.startswith('backup_') and f.endswith('.zip')]
        if len(backups) <= 1:
            _send_task_email(user_email, "Cleanup Backups", True, "Only one or no backups found. Nothing to cleanup.")
            return

        # Sort by mtime
        backups.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
        to_delete = backups[1:]
        
        deleted_count = 0
        for b in to_delete:
            os.remove(os.path.join(backup_dir, b))
            deleted_count += 1
            
        _send_task_email(user_email, "Cleanup Backups", True, f"Deleted {deleted_count} old backups.")
    except Exception as e:
        _send_task_email(user_email, "Cleanup Backups", False, str(e))

def create_backup_task(user_email):
    """
    Dump DB, zip DB + media.
    """
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"backup_{timestamp}.zip"
        zip_path = os.path.join(backup_dir, zip_filename)
        
        db_dump_path = os.path.join(backup_dir, f"db_dump_{timestamp}.json")
        
        # Dump DB using manage.py dumpdata
        # Note: In a production environment with Docker, you might need to specify the path to python/manage.py
        try:
            with open(db_dump_path, 'w') as f:
                subprocess.run(['python', 'manage.py', 'dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.Permission', '--indent', '2'], stdout=f, check=True)
        except Exception as dump_err:
             # Fallback to python3 if python is not available
             with open(db_dump_path, 'w') as f:
                subprocess.run(['python3', 'manage.py', 'dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.Permission', '--indent', '2'], stdout=f, check=True)
            
        # Create Zip
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add DB dump
            zipf.write(db_dump_path, arcname=os.path.basename(db_dump_path))
            
            # Add Media files
            media_root = settings.MEDIA_ROOT
            if os.path.exists(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # We want the 'media/' prefix in the zip
                        arcname = os.path.join('media', os.path.relpath(file_path, media_root))
                        zipf.write(file_path, arcname=arcname)
                    
        # Cleanup temp dump
        os.remove(db_dump_path)
            
        _send_task_email(user_email, "Create System Backup", True, f"Backup created: {zip_filename}")
    except Exception as e:
        logger.error(f"Backup failed: {e}\n{traceback.format_exc()}")
        _send_task_email(user_email, "Create System Backup", False, f"Error: {str(e)}")

def restore_backup_task(user_email, backup_name):
    """
    Destructive operation: Flush DB, Load Backup data, Restore Media.
    """
    temp_dir = None
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        zip_path = os.path.join(backup_dir, backup_name)
        
        if not os.path.exists(zip_path):
            raise Exception(f"Backup file {backup_name} not found.")

        # Create a temp directory for extraction
        temp_dir = tempfile.mkdtemp()
        
        # 1. Extract backup
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
            
        # 2. Find the JSON dump
        dump_files = [f for f in os.listdir(temp_dir) if f.startswith('db_dump_') and f.endswith('.json')]
        if not dump_files:
            raise Exception("No database dump found in the backup archive.")
        
        dump_path = os.path.join(temp_dir, dump_files[0])
        
        # 3. Flush Database (Destructive!)
        # We use --no-input to avoid interactive prompt
        try:
            subprocess.run(['python', 'manage.py', 'flush', '--no-input'], check=True)
        except:
            subprocess.run(['python3', 'manage.py', 'flush', '--no-input'], check=True)

        # 4. Load Data
        try:
            subprocess.run(['python', 'manage.py', 'loaddata', dump_path], check=True)
        except:
            subprocess.run(['python3', 'manage.py', 'loaddata', dump_path], check=True)

        # 5. Restore Media
        extracted_media = os.path.join(temp_dir, 'media')
        if os.path.exists(extracted_media):
            # Target media root
            target_media = settings.MEDIA_ROOT
            
            # Remove existing media safely
            if os.path.exists(target_media):
                shutil.rmtree(target_media)
            
            # Move extracted media to target location
            shutil.copytree(extracted_media, target_media)

        _send_task_email(user_email, "System Restore", True, f"System successfully restored from {backup_name}. You may need to log in again.")
    except Exception as e:
        logger.error(f"Restore failed: {e}\n{traceback.format_exc()}")
        _send_task_email(user_email, "System Restore", False, f"CRITICAL ERROR during restore: {str(e)}")
    finally:
        # Cleanup temp directory
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
