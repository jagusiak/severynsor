import cv2
import logging
from django.db import models
from django.utils import timezone
from django.core.files.base import ContentFile
from .sensor_retriever import SensorRetriever
from .record import ImageRecord
from ..db_fields import EncryptedCharField

logger = logging.getLogger(__name__)

class RTSPRetriever(SensorRetriever):
    rtsp_url = EncryptedCharField(max_length=512)

    retriever_name = 'RTSP Retriever'
    
    @classmethod
    def get_retriever_tile_html(cls):
        return """
        <div class="flex flex-col items-center p-6 bg-white dark:bg-base-900 rounded-xl shadow-sm border border-base-200 dark:border-base-800 hover:border-primary-500 transition-all cursor-pointer h-full">
            <h3 class="text-xl font-bold mb-3 text-gray-900 dark:text-gray-100">RTSP Stream</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400 text-center mb-4 truncate w-full">Capture images from RTSP video streams.</p>
            <div class="mt-auto flex flex-wrap justify-center gap-1.5">
                <span class="px-2 py-0.5 rounded-md bg-base-100 dark:bg-base-800 text-[10px] uppercase font-bold text-gray-500 dark:text-gray-400 border border-base-200 dark:border-base-700">Image Streaming</span>
            </div>
        </div>
        """

    def grab_data(self):
        # validation for image sensor is handled in clean.
        logger.info(f"Grabbing image from RTSP URL: {self.rtsp_url}")
        cap = cv2.VideoCapture(self.rtsp_url)
        if not cap.isOpened():
            raise Exception(f"Failed to open RTSP stream: {self.rtsp_url}")

        ret, frame = cap.read()
        cap.release()
        
        if ret:
            # Try to grab an image encoded in jpg correctly
            ret_img, buffer = cv2.imencode('.jpg', frame)
            if ret_img:
                image_content = ContentFile(buffer.tobytes(), name=f"rtsp_{self.id}_{timezone.now().timestamp()}.jpg")
                ImageRecord.objects.create(
                    sensor=self.sensor,
                    timestamp=timezone.now(),
                    image=image_content
                )
                logger.debug(f"Successfully grabbed and saved image from {self.rtsp_url}")
            else:
                raise Exception(f"Failed to encode image from {self.rtsp_url}")
        else:
            raise Exception(f"Failed to read frame from RTSP stream: {self.rtsp_url}")


