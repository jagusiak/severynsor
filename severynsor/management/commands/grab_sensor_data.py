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
        from django_q.tasks import async_task
        from severynsor.tasks import grab_data_task

        retrievers = SensorRetriever.objects.all()
        count = 0
        self.stdout.write(self.style.NOTICE(f'Checking {retrievers.count()} retrievers...'))
        
        for retriever in retrievers:
            if retriever.should_run():
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} should run. Scheduling async task...'))
                async_task(grab_data_task, retriever.id)
                count += 1
            else:
                self.stdout.write(self.style.NOTICE(f'Retriever {retriever} skipped (already ran for this period).'))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully scheduled {count} tasks.'))
