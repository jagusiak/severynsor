import asyncio
import cv2
import av
import numpy as np
import time
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist

class VideoStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.retriever_id = self.scope['url_route']['kwargs'].get('retriever_id')
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return

        self.streaming = True
        self.queue = asyncio.Queue(maxsize=3) # Small queue to ensure real-time and avoid memory build-up
        await self.accept()
        
        self.stream_task = asyncio.create_task(self.stream_video())
        self.send_task = asyncio.create_task(self.sender())

    async def disconnect(self, close_code):
        self.streaming = False
        if hasattr(self, 'stream_task'):
            self.stream_task.cancel()
        if hasattr(self, 'send_task'):
            self.send_task.cancel()

    async def sender(self):
        """Asynchronously sends images from the queue to the WebSocket."""
        try:
            while self.streaming:
                data = await self.queue.get()
                await self.send(bytes_data=data)
                self.queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"WebSocket sender error: {e}")
        finally:
            await self.close()

    async def stream_video(self):
        """Handles video decoding in a thread pool and passes frames to the sender queue."""
        from .models.rtsp_retriever import RTSPRetriever
        
        container = None
        loop = asyncio.get_event_loop()
        
        try:
            retriever = await sync_to_async(RTSPRetriever.objects.get)(id=self.retriever_id)
            rtsp_url = retriever.rtsp_url
            
            # Opening the container is blocking
            container = await loop.run_in_executor(
                None, 
                lambda: av.open(rtsp_url, options={'rtsp_transport': 'tcp', 'stimeout': '5000000'})
            )
            
            stream = container.streams.video[0]
            
            def decode_loop():
                last_frame_time = 0
                # Limit to ~15 FPS to save bandwidth and prevent event loop congestion
                frame_interval = 1.0 / 15.0 
                
                try:
                    for frame in container.decode(stream):
                        if not self.streaming:
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
                    print(f"Internal decoding error: {e}")

            await loop.run_in_executor(None, decode_loop)

        except ObjectDoesNotExist:
            print(f"Retriever {self.retriever_id} not found")
        except Exception as e:
            print(f"Streaming task error: {e}")
        finally:
            self.streaming = False
            if container:
                try:
                    await loop.run_in_executor(None, container.close)
                except:
                    pass
            # Trigger sender to exit
            loop.call_soon_threadsafe(self.queue.put_nowait, None) if not self.queue.full() else None
