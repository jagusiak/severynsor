import os
import subprocess
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Optimizes all images in the media directory recursively'

    def handle(self, *args, **options):
        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            self.stdout.write(self.style.ERROR(f"Media directory not found: {media_root}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Starting optimization of images in: {media_root}"))
        
        try:
            # -p 2: use 2 processes (can adjust or remove for default)
            # --quiet: less output
            # media_root: the path to process
            result = subprocess.run(
                ['optimize-images', media_root], 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("Image optimization completed successfully."))
                if result.stdout:
                    self.stdout.write(result.stdout)
            else:
                self.stdout.write(self.style.ERROR(f"Optimization failed with error:\n{result.stderr}"))
                
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("The 'optimize-images' command was not found. Please ensure it is installed."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {str(e)}"))
