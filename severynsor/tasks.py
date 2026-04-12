from django.utils import timezone
from severynsor.models import SensorRetriever
from severynsor.models.log import ActivityLog
import traceback
import logging

logger = logging.getLogger(__name__)

def grab_data_task(retriever_id):
    """
    Task to execute a single retriever's grab_data method.
    """
    try:
        retriever = SensorRetriever.objects.get(pk=retriever_id)
    except SensorRetriever.DoesNotExist:
        logger.error(f"Retriever {retriever_id} does not exist.")
        return

    # Note: we don't check should_run() here because the command 
    # that schedules this task already checked it. 
    # However, if we want to be safe (e.g. if the task stayed in queue for long), 
    # we could check it again.
    
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
