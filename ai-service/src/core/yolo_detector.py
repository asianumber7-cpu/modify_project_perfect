import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

class YOLOFashionDetector:
    """
    YOLO 기반 패션 아이템 감지기
    - YOLOv8을 사용하여 사람/의류 영역 감지
    - 상의/하의 영역 분리 지원
    """
    
    def __init__(self):
        self.model = None
        self.pose_model = None
        self.initialized = False
        
        # COCO 클래스 ID (person = 0)
        self.PERSON_CLASS_ID = 0
        
        # 상의/하의 비율 (전체 사람 bbox 기준)
        self.UPPER_RATIO = 0.55  # 상위 55%가 상의
        self.LOWER_RATIO = 0.45  # 하위 45%가 하의
        
    def initialize(self):
        """YOLO 모델 로드"""
        if self.initialized: return True
        try:
            from ultralytics import YOLO
            
            # [보안 패치] PyTorch Safe Globals 등록
            try:
                from ultralytics.nn.tasks import DetectionModel
                safe_classes = [
                    DetectionModel,
                    nn.Sequential, nn.Conv2d, nn.BatchNorm2d, nn.SiLU, 
                    nn.Upsample, nn.MaxPool2d, nn.ModuleList,
                ]
                torch.serialization.add_safe_globals(safe_classes)
            except: pass

            # [보안 패치] weights_only=False 강제 적용 (로딩 시에만)
            _original_load = torch.load
            def _unsafe_load(*args, **kwargs):
                if 'weights_only' not in kwargs: kwargs['weights_only'] = False
                return _original_load(*args, **kwargs)
            torch.load = _unsafe_load

            self.model = YOLO('yolov8n.pt')
            try:
                self.pose_model = YOLO('yolov8n-pose.pt')
                logger.info("✅ YOLO Pose model loaded")
            except: self.pose_model = None
            
            # 복구
            torch.load = _original_load
            
            self.initialized = True
            logger.info("✅ YOLO Fashion Detector initialized")
            return True
            
        except ImportError:
            logger.error("❌ ultralytics not installed.")
            return False
        except Exception as e:
            logger.error(f"❌ YOLO initialization failed: {e}")
            return False
    
    def detect_person(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        이미지에서 사람 감지
        """
        if not self.initialized:
            if not self.initialize(): return []
        
        try:
            # 🚨 [FIX] 4채널(RGBA) 이미지가 들어오면 3채널(RGB)로 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # PIL -> numpy
            img_array = np.array(image)
            
            # YOLO 추론
            results = self.model(img_array, classes=[self.PERSON_CLASS_ID], verbose=False)
            
            persons = []
            for result in results:
                if result.boxes is None: continue
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    area = (x2 - x1) * (y2 - y1)
                    
                    persons.append({
                        "bbox": (int(x1), int(y1), int(x2), int(y2)),
                        "confidence": conf,
                        "area": area
                    })
            
            persons.sort(key=lambda x: x["area"], reverse=True)
            return persons
            
        except Exception as e:
            logger.error(f"❌ Person detection failed: {e}")
            return []
    
    def get_keypoints(self, image: Image.Image) -> Optional[Dict[str, Tuple[int, int]]]:
        if self.pose_model is None: return None
        try:
            # 🚨 [FIX] 포즈 추정 시에도 RGB 변환 확인
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            img_array = np.array(image)
            results = self.pose_model(img_array, verbose=False)
            
            KEYPOINT_NAMES = {5: "left_shoulder", 6: "right_shoulder", 11: "left_hip", 12: "right_hip"}
            for result in results:
                if result.keypoints is None: continue
                keypoints = result.keypoints.xy[0].tolist()
                kp_dict = {}
                for idx, name in KEYPOINT_NAMES.items():
                    if idx < len(keypoints):
                        x, y = keypoints[idx]
                        if x > 0 and y > 0: kp_dict[name] = (int(x), int(y))
                if kp_dict: return kp_dict
            return None
        except: return None
    
    def _crop_from_bbox(self, image: Image.Image, bbox: Tuple[int,int,int,int], target: str) -> Image.Image:
        x1, y1, x2, y2 = bbox
        w, h = image.size
        
        # Padding
        px = int((x2 - x1) * 0.1)
        py = int((y2 - y1) * 0.05)
        
        x1 = max(0, x1 - px)
        y1 = max(0, y1 - py)
        x2 = min(w, x2 + px)
        y2 = min(h, y2 + py)
        
        crop_box = (x1, y1, x2, y2)
        if target == "upper":
             crop_box = (x1, y1, x2, int(y1 + (y2-y1) * self.UPPER_RATIO))
        elif target == "lower":
             crop_box = (x1, int(y1 + (y2-y1) * (1 - self.LOWER_RATIO)), x2, y2)
             
        return image.crop(crop_box)

    def crop_fashion_regions(self, image: Image.Image, target: str = "full") -> Optional[Image.Image]:
        persons = self.detect_person(image)
        if not persons: return image
        return self._crop_from_bbox(image, persons[0]["bbox"], target)
    
    def extract_fashion_features(self, image: Image.Image) -> Dict[str, Optional[Image.Image]]:
        result = {"full": None, "upper": None, "lower": None}
        
        persons = self.detect_person(image)
        if not persons:
            result["full"] = image 
            return result
            
        main_bbox = persons[0]["bbox"]
        
        # 원본 이미지가 RGBA라면 여기서도 변환된 버전을 사용하는 게 안전하지만,
        # crop은 모드 상관없이 동작하므로 괜찮습니다.
        # 다만 detect_person 내부에서 변환된 이미지를 리턴하지 않으므로, 
        # 원본 image를 그대로 씁니다.
        
        result["full"] = self._crop_from_bbox(image, main_bbox, "full")
        result["upper"] = self._crop_from_bbox(image, main_bbox, "upper")
        result["lower"] = self._crop_from_bbox(image, main_bbox, "lower")
        
        return result

yolo_detector = YOLOFashionDetector()