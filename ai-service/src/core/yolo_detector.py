import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np

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
        if self.initialized:
            return True
            
        try:
            from ultralytics import YOLO
            
            # YOLOv8 nano 모델 (가볍고 빠름)
            self.model = YOLO('yolov8n.pt')
            
            # Pose 모델 (선택적 - 더 정확한 상/하의 분리)
            try:
                self.pose_model = YOLO('yolov8n-pose.pt')
                logger.info("✅ YOLO Pose model loaded")
            except Exception as e:
                logger.warning(f"⚠️ YOLO Pose model not available: {e}")
                self.pose_model = None
            
            self.initialized = True
            logger.info("✅ YOLO Fashion Detector initialized")
            return True
            
        except ImportError:
            logger.error("❌ ultralytics not installed. Run: pip install ultralytics")
            return False
        except Exception as e:
            logger.error(f"❌ YOLO initialization failed: {e}")
            return False
    
    def detect_person(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        이미지에서 사람 감지
        
        Returns:
            List of detected persons with bboxes
            [{"bbox": (x1, y1, x2, y2), "confidence": 0.95, "area": 10000}, ...]
        """
        if not self.initialized:
            if not self.initialize():
                return []
        
        try:
            # PIL -> numpy
            img_array = np.array(image)
            
            # YOLO 추론
            results = self.model(img_array, classes=[self.PERSON_CLASS_ID], verbose=False)
            
            persons = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                    
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    area = (x2 - x1) * (y2 - y1)
                    
                    persons.append({
                        "bbox": (int(x1), int(y1), int(x2), int(y2)),
                        "confidence": conf,
                        "area": area
                    })
            
            # 면적 기준 내림차순 정렬 (가장 큰 사람 우선)
            persons.sort(key=lambda x: x["area"], reverse=True)
            
            logger.info(f"🎯 Detected {len(persons)} person(s)")
            return persons
            
        except Exception as e:
            logger.error(f"❌ Person detection failed: {e}")
            return []
    
    def get_keypoints(self, image: Image.Image) -> Optional[Dict[str, Tuple[int, int]]]:
        """
        Pose 모델로 키포인트 추출 (어깨, 엉덩이 등)
        
        Returns:
            {"left_shoulder": (x, y), "right_shoulder": (x, y), 
             "left_hip": (x, y), "right_hip": (x, y), ...}
        """
        if self.pose_model is None:
            return None
            
        try:
            img_array = np.array(image)
            results = self.pose_model(img_array, verbose=False)
            
            # COCO keypoint indices
            KEYPOINT_NAMES = {
                5: "left_shoulder",
                6: "right_shoulder",
                11: "left_hip",
                12: "right_hip",
                13: "left_knee",
                14: "right_knee"
            }
            
            for result in results:
                if result.keypoints is None:
                    continue
                    
                keypoints = result.keypoints.xy[0].tolist()
                
                kp_dict = {}
                for idx, name in KEYPOINT_NAMES.items():
                    if idx < len(keypoints):
                        x, y = keypoints[idx]
                        if x > 0 and y > 0:  # valid keypoint
                            kp_dict[name] = (int(x), int(y))
                
                if kp_dict:
                    return kp_dict
                    
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Keypoint detection failed: {e}")
            return None
    
    def crop_fashion_regions(
        self, 
        image: Image.Image,
        target: str = "full"  # "full", "upper", "lower"
    ) -> Optional[Image.Image]:
        """
        이미지에서 패션 영역 크롭
        
        Args:
            image: 입력 이미지
            target: "full" (전신), "upper" (상의), "lower" (하의)
            
        Returns:
            크롭된 이미지 또는 None
        """
        # 사람 감지
        persons = self.detect_person(image)
        
        if not persons:
            logger.warning("⚠️ No person detected, returning original image")
            return image
        
        # 가장 큰 사람 선택
        main_person = persons[0]
        x1, y1, x2, y2 = main_person["bbox"]
        
        # 이미지 크기
        img_w, img_h = image.size
        
        # bbox 약간 확장 (여유 공간)
        padding_x = int((x2 - x1) * 0.1)
        padding_y = int((y2 - y1) * 0.05)
        
        x1 = max(0, x1 - padding_x)
        y1 = max(0, y1 - padding_y)
        x2 = min(img_w, x2 + padding_x)
        y2 = min(img_h, y2 + padding_y)
        
        person_height = y2 - y1
        
        if target == "full":
            # 전신 크롭
            crop_box = (x1, y1, x2, y2)
            
        elif target == "upper":
            # 상의 크롭 (상위 55%)
            # Pose 키포인트가 있으면 더 정확하게
            keypoints = self.get_keypoints(image)
            
            if keypoints and "left_hip" in keypoints and "right_hip" in keypoints:
                # 엉덩이 위치 기준
                hip_y = (keypoints["left_hip"][1] + keypoints["right_hip"][1]) // 2
                upper_y2 = min(hip_y + 20, y2)  # 엉덩이 아래 약간
            else:
                # 비율 기반
                upper_y2 = int(y1 + person_height * self.UPPER_RATIO)
            
            crop_box = (x1, y1, x2, upper_y2)
            
        elif target == "lower":
            # 하의 크롭 (하위 45%)
            keypoints = self.get_keypoints(image)
            
            if keypoints and "left_hip" in keypoints and "right_hip" in keypoints:
                # 엉덩이 위치 기준
                hip_y = (keypoints["left_hip"][1] + keypoints["right_hip"][1]) // 2
                lower_y1 = max(hip_y - 20, y1)  # 엉덩이 위 약간
            else:
                # 비율 기반
                lower_y1 = int(y1 + person_height * (1 - self.LOWER_RATIO))
            
            crop_box = (x1, lower_y1, x2, y2)
            
        else:
            logger.warning(f"⚠️ Unknown target: {target}, using full")
            crop_box = (x1, y1, x2, y2)
        
        # 크롭 실행
        cropped = image.crop(crop_box)
        
        logger.info(f"✂️ Cropped {target} region: {crop_box} -> {cropped.size}")
        
        return cropped
    
    def extract_fashion_features(
        self, 
        image: Image.Image
    ) -> Dict[str, Optional[Image.Image]]:
        """
        이미지에서 상의/하의/전신 모두 추출
        
        Returns:
            {
                "full": Image,
                "upper": Image,
                "lower": Image
            }
        """
        result = {
            "full": None,
            "upper": None,
            "lower": None
        }
        
        # 사람 감지
        persons = self.detect_person(image)
        
        if not persons:
            # 사람 없으면 원본 반환
            result["full"] = image
            return result
        
        # 각 영역 크롭
        result["full"] = self.crop_fashion_regions(image, "full")
        result["upper"] = self.crop_fashion_regions(image, "upper")
        result["lower"] = self.crop_fashion_regions(image, "lower")
        
        return result


# 싱글톤 인스턴스
yolo_detector = YOLOFashionDetector()