import asyncio
import cv2
import av
import numpy as np
import time
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone


logger = logging.getLogger(__name__)

class VideoStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.retriever_id = self.scope['url_route']['kwargs'].get('retriever_id')
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            logger.warning(f"Unauthorized access attempt to video stream for retriever {self.retriever_id}")
            await self.close()
            return

        self.streaming = True
        self.queue = asyncio.Queue(maxsize=3) # Small queue to ensure real-time and avoid memory build-up
        await self.accept()
        
        logger.info(f"Accepted WebSocket connection for video stream retriever {self.retriever_id}")
        self.stream_task = asyncio.create_task(self.stream_video())
        self.send_task = asyncio.create_task(self.sender())

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected with code {close_code} for retriever {self.retriever_id}")
        self.streaming = False
        if hasattr(self, 'stream_task'):
            self.stream_task.cancel()
        if hasattr(self, 'send_task'):
            self.send_task.cancel()
        
        try:
            if hasattr(self, 'stream_task'):
                await self.stream_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(f"Error during stream_task cancellation: {e}")

    async def sender(self):
        """Asynchronously sends images from the queue to the WebSocket."""
        try:
            while self.streaming:
                try:
                    data = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                if data is None:
                    self.queue.task_done()
                    break
                await self.send(bytes_data=data)
                self.queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"WebSocket sender error for retriever {self.retriever_id}: {e}")
        finally:
            self.streaming = False
            await self.close()

    async def stream_video(self):
        """Handles video decoding in a thread pool and passes frames to the sender queue."""
        from .models.rtsp_retriever import RTSPRetriever
        from .models.log import ActivityLog
        
        container = None
        loop = asyncio.get_event_loop()
        start_time = timezone.now()
        
        try:
            retriever = await sync_to_async(RTSPRetriever.objects.get)(id=self.retriever_id)
            rtsp_url = retriever.rtsp_url.strip()
            
            logger.info(f"Starting RTSP stream from {rtsp_url}")
            
            # Opening the container is blocking
            try:
                # Use a slightly shorter timeout for initial connection
                container = await loop.run_in_executor(
                    None, 
                    lambda: av.open(rtsp_url, options={'rtsp_transport': 'tcp', 'stimeout': '3000000'})
                )
            except Exception as e:
                # If TCP fails or returns 400, try without forcing transport (allows UDP fallback)
                logger.warning(f"Initial RTSP connection (TCP) failed for {rtsp_url}: {e}. Retrying with fallback...")
                if not self.streaming:
                    return
                    
                try:
                    container = await loop.run_in_executor(
                        None, 
                        lambda: av.open(rtsp_url, options={'stimeout': '5000000'})
                    )
                except Exception as ex:
                    logger.error(f"RTSP stream connection failed for {rtsp_url}: {ex}")
                    await sync_to_async(ActivityLog.objects.create)(
                        type=ActivityLog.LIVE_STREAM,
                        sensor=retriever.sensor,
                        retriever=retriever,
                        success=False,
                        error_message=f"Live stream connection failed: {ex}",
                        timestamp=start_time
                    )
                    return
            
            if not container.streams.video:
                error_msg = f"No video streams found in {rtsp_url}"
                logger.error(error_msg)
                await sync_to_async(ActivityLog.objects.create)(
                    type=ActivityLog.LIVE_STREAM,
                    sensor=retriever.sensor,
                    retriever=retriever,
                    success=False,
                    error_message=error_msg,
                    timestamp=start_time
                )
                return

            stream = container.streams.video[0]
            
            def decode_loop():
                last_frame_time = 0
                # Limit to ~15 FPS to save bandwidth and prevent event loop congestion
                frame_interval = 1.0 / 15.0 
                
                try:
                    for frame in container.decode(stream):
                        if not self.streaming:
                            logger.debug("Stopping decode loop due to self.streaming being False")
                            break
                        
                        now = time.time()
                        if now - last_frame_time < frame_interval:
                            continue
                        last_frame_time = now
                        
                        # Process image
                        img = frame.to_ndarray(format='bgr24')
                        # Encode with specific quality to balance bandwidth/quality
                        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        encoded_data = buffer.tobytes()
                        
                        # Thread-safe way to update the queue in the event loop
                        def update_queue():
                            if not self.streaming:
                                return
                            if self.queue.full():
                                try:
                                    self.queue.get_nowait()
                                    self.queue.task_done()
                                except (asyncio.QueueEmpty, ValueError):
                                    pass
                            try:
                                self.queue.put_nowait(encoded_data)
                            except asyncio.QueueFull:
                                pass
                        
                        loop.call_soon_threadsafe(update_queue)
                except Exception as e:
                    if self.streaming:
                        logger.error(f"Internal decoding error for retriever {self.retriever_id}: {e}")
                    else:
                        logger.debug(f"Decoding loop interrupted: {e}")

            await loop.run_in_executor(None, decode_loop)

        except ObjectDoesNotExist:
            logger.error(f"Retriever {self.retriever_id} not found")
        except asyncio.CancelledError:
            logger.debug(f"Streaming task for retriever {self.retriever_id} cancelled")
        except Exception as e:
            logger.exception(f"Streaming task error for retriever {self.retriever_id}: {e}")
            try:
                # Try to log to ActivityLog if we have the retriever info
                retriever = await sync_to_async(RTSPRetriever.objects.get)(id=self.retriever_id)
                await sync_to_async(ActivityLog.objects.create)(
                    type=ActivityLog.LIVE_STREAM,
                    sensor=retriever.sensor,
                    retriever=retriever,
                    success=False,
                    error_message=f"Live stream error: {e}",
                    timestamp=start_time
                )
            except:
                pass
        finally:
            self.streaming = False
            if container:
                logger.info(f"Closing RTSP container for retriever {self.retriever_id}")
                try:
                    # Closing the container can also block, so run in executor
                    await loop.run_in_executor(None, container.close)
                except Exception as e:
                    logger.error(f"Error while closing RTSP container: {e}")
            
            # Send None to queue to signal sender to exit, if loop is still running
            if loop.is_running():
                loop.call_soon_threadsafe(lambda: self.queue.put_nowait(None) if not self.queue.full() else None)

