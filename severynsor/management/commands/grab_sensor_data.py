from django.core.management.base import BaseCommand
from severynsor.models import SensorRetriever
from severynsor.models.log import ActivityLog
from django.utils import timezone
import traceback

class Command(BaseCommand):
    help = 'Grabs sensor data from all configured retrievers'

    def handle(self, *args, **options):
        import os
        import fcntl
        from django.conf import settings
        
        # Use lock file path from settings
        lock_file_path = settings.GRAB_DATA_LOCK_FILE
        
        # Open (or create) the lock file
        self.lock_file = open(lock_file_path, 'w')
        
        try:
            # Try to acquire an exclusive lock without blocking (LOCK_NB)
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            self.stdout.write(self.style.WARNING('Data retrieval is already in progress. Skipping this run.'))
            return

        try:
            self._do_grab_data()
        finally:
            # Release the lock and close the file
            fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            self.lock_file.close()

    def _do_grab_data(self):
        retrievers = SensorRetriever.objects.all()
        count = 0
        self.stdout.write(self.style.NOTICE(f'Checking {retrievers.count()} retrievers...'))
        
        for retriever in retrievers:
            if retriever.should_run():
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} should run. Grabbing data...'))
                start_time = timezone.now()
                try:
                    retriever.grab_data()
                    count += 1
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=True,
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
                except NotImplementedError:
                    self.stdout.write(self.style.WARNING(f'Retriever {retriever} has not implemented grab_data().'))
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=False,
                        error_message="Retriever has not implemented grab_data().",
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error running retriever {retriever}: {e}'))
                    ActivityLog.objects.create(
                        type=ActivityLog.RETRIEVER,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=False,
                        error_message=f"{str(e)}\n{traceback.format_exc()}",
                        timestamp=start_time,
                        duration=(timezone.now() - start_time).total_seconds()
                    )
            else:
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} skipped (already ran for this period).'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully grabbed data for {count} retrievers.'))
