import os
import shutil
import glob
import gc
import re
import math
import random
import json
import numpy as np
import pandas as pd
from tqdm import tqdm
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from copy import deepcopy
from typing import List, Tuple, Dict, Any

from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags, ImageFilter
import matplotlib.pyplot as plt
import io
import cv2

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import cdist

from paddleocr import PaddleOCR, draw_ocr
import paddle

# from ultralytics import YOLO

# from azure.ai.formrecognizer import DocumentAnalysisClient
# from azure.core.credentials import AzureKeyCredential

# import boto3

# from annotate import *

gc.collect()


###############################################################################################################
# 바운딩 박스 전처리
###############################################################################################################  

def sort_paddle_boxes(azure_boxes, azure_txts, paddle_boxes, paddle_txts):
    # Azure의 bbox 중심점 계산
    azure_centers = [(np.mean([p[0] for p in box]), np.mean([p[1] for p in box])) for box in azure_boxes]
    # Paddle의 bbox 중심점 계산
    paddle_centers = [(np.mean([p[0] for p in box]), np.mean([p[1] for p in box])) for box in paddle_boxes]

    # 거리 행렬 계산 (Azure 중심점과 Paddle 중심점 간의 거리)
    distance_matrix = cdist(azure_centers, paddle_centers, metric='euclidean')

    # 가장 가까운 매칭을 찾기 위해 인덱스 정렬
    matched_indices = np.argmin(distance_matrix, axis=1)

    # 정렬된 Paddle 결과 생성
    sorted_paddle_boxes = [paddle_boxes[i] for i in matched_indices]
    sorted_paddle_txts = [paddle_txts[i] for i in matched_indices]

    return sorted_paddle_boxes, sorted_paddle_txts
    
def sort_bounding_box(coord: List[List[int]]) -> List[List[int]]:
    """
    bbox(4개 좌표) 정보를 받아 아래 순서로 정렬하는 함수
        [left_top, right_top, right_bottom, left_bottom]
    ex.)
            1  2
            4  3

    Args:
        coord: bbox의 4개 좌표
            [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]

    Returns: 정렬된 bbox
        [[left_top], [right_top], [right_bottom], [left_bottom]]
    """
    # y좌표 기준으로 내림차순 정렬
    sorted_coord = sorted(coord, key=lambda x: x[1])

    # top 좌표 2개를 x좌표 기준으로 정렬
    top_coord = sorted_coord[:2]
    left_top, right_top = sorted(top_coord, key=lambda x: x[0])

    # bottom 좌표 2개를 x좌표 기준으로 정렬
    bottom_coord = sorted_coord[2:]
    left_bottom, right_bottom = sorted(bottom_coord, key=lambda x: x[0])

    return [left_top, right_top, right_bottom, left_bottom]


def two_to_four_coord(coord: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    2개 좌표(left top, right bottom)만 있는 bbox를 받아 
    4개 좌표(left_top, right_top, right_bottom, left_bottom)로 변환하는 함수

    Args:
        coord: bbox의 2개 좌표
            [[left_top], [right_bottom]]

    Returns: bbox의 4개 좌표
        [[left_top], [right_top], [right_bottom], [left_bottom]]
    """
    left_top, right_bottom = coord
    left_bottom = [left_top[0], right_bottom[1]]
    right_top = [right_bottom[0], left_top[1]]
    return [left_top, right_top, right_bottom, left_bottom]


def normalize_bbox(x_min, y_min, x_max, y_max, img_width, img_height):
    """YOLO 형식으로 정규화하는 함수"""
    x_center = (x_min + x_max) / 2 / img_width
    y_center = (y_min + y_max) / 2 / img_height
    width = (x_max - x_min) / img_width
    height = (y_max - y_min) / img_height
    return f"{x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"


def denormalize_bbox(x_center, y_center, width, height, img_width, img_height):
    """YOLO 형식에서 원본 이미지 픽셀 좌표로 변환하는 함수"""
    x_center *= img_width
    y_center *= img_height
    width *= img_width
    height *= img_height

    x_min = x_center - (width / 2)
    y_min = y_center - (height / 2)
    x_max = x_center + (width / 2)
    y_max = y_center + (height / 2)

    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]


def convert_to_yolo(ocr_dict=None, yolo_dict=None, input_size=None, img_width=None, img_height=None):
    """
    OCR 데이터 또는 YOLO 예측 데이터를 YOLO 형식으로 변환하는 함수.
    
    - ocr_dict: OCR 박스 데이터 (dictionary)
    - yolo_dict: YOLO 예측 박스 데이터 (dictionary)
    - input_size: YOLO 모델 입력 크기 (예: 1024)
    - img_width, img_height: 원본 이미지 크기
    - ignore_label: 특정 라벨을 무시하고 필터링 (기본값: '#')
    - yolo_class: YOLO 라벨 클래스 ID (기본값: 0)
    
    반환값: YOLO 형식의 문자열 리스트
    """
    yolo_labels = []

    # OCR 데이터 변환
    if ocr_dict:
        for obj in ocr_dict.values():
            if obj["label"] == "#":
                continue  # 특정 라벨 제외
            
            bbox = obj["bbox"]
            x_min = min(p[0] for p in bbox)
            y_min = min(p[1] for p in bbox)
            x_max = max(p[0] for p in bbox)
            y_max = max(p[1] for p in bbox)

            yolo_labels.append(f"0 " + normalize_bbox(x_min, y_min, x_max, y_max, img_width, img_height))

    # YOLO 모델 예측 데이터 변환
    if yolo_dict and input_size:
        for item in yolo_dict.values():
            if item["label"] != 0:
                continue  # label이 0이 아닌 경우 무시

            x_min, y_min = item["bbox"][0]
            x_max, y_max = item["bbox"][1]

            x_min = (x_min / input_size) * img_width
            y_min = (y_min / input_size) * img_height
            x_max = (x_max / input_size) * img_width
            y_max = (y_max / input_size) * img_height

            yolo_labels.append(f"1 " + normalize_bbox(x_min, y_min, x_max, y_max, img_width, img_height))

    return yolo_labels


def yolo_to_bbox(yolo_labels, img_width, img_height):
    """YOLO 형식 라벨을 Bounding Box 좌표 리스트로 변환하는 함수"""
    bboxes = []
    labels = []
    
    for line in yolo_labels:
        parts = line.strip().split()
        label, x_center, y_center, width, height = map(float, parts)
        bbox = denormalize_bbox(x_center, y_center, width, height, img_width, img_height)
        
        bboxes.append(bbox)
        labels.append(str(label))
    return bboxes, labels


def resize_bboxes(bboxes, original_size, new_size):
    """Bounding Box 좌표를 새로운 이미지 크기에 맞게 조정하는 함수"""
    W_original, H_original = original_size
    W_new, H_new = new_size

    # 크기 비율 계산
    x_scale = W_new / W_original
    y_scale = H_new / H_original

    # 모든 bbox 좌표 변환
    resized_bboxes = [
        [[int(x * x_scale), int(y * y_scale)] for x, y in bbox] for bbox in bboxes
    ]

    return resized_bboxes

def group_bboxes(
    bboxes: List[List[Tuple[int, int]]], 
    labels: List[str], 
    input_size: int = 2048
) -> List[List[Tuple[Tuple[int, int], Tuple[int, int], str]]]:
    """
    bbox와 label을 받아 가까이에 있다고 판단되는 bbox끼리 묶어 그룹핑하는 함수

    Args:
        bboxes: bbox(2개 좌표) 정보가 담겨있는 리스트
            [
                [[left_top], [right_bottom],
                [[left_top], [right_bottom],
                ...
            ]
        labels: label 정보가 담겨있는 리스트

    Returns: 그룹핑된 bbox 정보가 담겨있는 리스트
        groups:
            [
                [[[left_top], [right_bottom], label]],
                [[[left_top], [right_bottom], label], [[left_top], [right_bottom], label]], # 2개 bbox가 그룹핑됨
                ...
            ]
    """
    box_info = [box+[label] for box, label in zip(bboxes, labels)]
    # left_top의 y좌표 기준으로 내림차순 정렬
    box_info = list(sorted(box_info, key=lambda x: x[0][1]))
    # left_top과 right_bottom의 중심점 계산
    def calculate_center(bbox):
        (x1, y1), (x2, y2), _ = bbox
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        return (center_x, center_y)
    box_info = [(calculate_center(bbox), bbox) for bbox in box_info]
    # 중심점 좌표 간의 차이를 비교해 가까이 있는 좌표들을 그룹핑
    # 2048x2048 사이즈 이미지 기준 (x좌표 임계값 = 40, y좌표 임계값 =2)
    x_th = 50*input_size/2048
    y_th = 5*input_size/2048

    def find_group(center, bbox, centers):
        group = [bbox]
        for other_center, other_bbox in centers:
            _, _,  label = other_bbox
            x, y = center
            xi, yi = other_center
            if (0 < abs(x - xi) < x_th) and (0 < abs(y - yi) < y_th):
                group.append(other_bbox)
        return group

    groups = []
    for center, box in box_info:
        # x좌표 기준으로 정렬
        group = list(sorted(find_group(center, box, box_info)))
        if group not in groups:
            groups.append(group)
    return groups


def get_peak(coord: List[List[int]]) -> List[List[int]]:
    """
    bbox의 4개 좌표 중 가장 바깥에 있는 지점을 조합하여 좌표 반환

    Args:
        coord: bbox(4개 좌표) 정보
            [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]

    Returns: 가장 바깥에 있는 4개 좌표
        [[outermost_left_top], [outermost_right_top], [outermost_right_bottom], [outermost_left_bottom]]
    """
    # [left_top, right_top, right_bottom, left_bottom] 순서로 정렬
    coord = sort_bounding_box(coord)
    for i in range(len(coord)):
        globals()[f"x{i}"], globals()[f"y{i}"] = coord[i]

    # [left_top과 left_bottom 중 더 바깥쪽에 있는 x좌표, right_bottom과 left_bottom 중 더 바깥쪽에 있는 y좌표]
    outermost_left_top = [min(x0, x3), min(y0, y1)]

    # [right_top과 right_bottom 중 더 바깥쪽에 있는 x좌표, left_top과 right_top 중 더 바깥쪽에 있는 y좌표]
    outermost_right_bottom = [max(x1, x2), max(y2, y3)]

    outermost_right_top = [outermost_right_bottom[0], outermost_left_top[1]]
    outermost_left_bottom = [outermost_left_top[0], outermost_right_bottom[1]]

    return [outermost_left_top, outermost_right_top, outermost_right_bottom, outermost_left_bottom]


def refine_group_bbox(
    groups: List[List[Tuple[Tuple[int, int], Tuple[int, int], str]]]
) -> Tuple[List[List[Tuple[int, int]]], List[str]]:
    """
    각 그룹 내의 그룹핑된 bbox의 좌표 중 가장 바깥에 있는 지점을 조합해 하나의 bbox로 변환하는 함수

    Args:
        groups: 그룹핑된 bbox(2개 좌표) 정보가 담겨있는 리스트
            [
                [[[left_top], [right_bottom], label]],
                [[[left_top], [right_bottom], label], [[left_top], [right_bottom], label]], # 2개 bbox가 그룹핑됨
                ...
            ]

    Returns: 
        bboxes: bbox(2개 좌표) 정보가 담겨있는 리스트
            [
                [[left_top], [right_bottom],
                [[left_top], [right_bottom],
                ...
            ]
        labels: label 정보가 담겨있는 리스트
    """
    bboxes = []
    labels = []
    for box in groups:
        if len(box) > 1:
            # 그룹핑된 
            tmp = box[0][:-1]+box[-1][:-1]
            bbox = get_peak(tmp)
            label = ''.join([str(item[-1]) for item in box])
        else:
            bbox = two_to_four_coord(box[0][:-1])
            label = str(box[0][-1])
        bboxes.append(bbox)
        labels.append(label)
    return bboxes, labels


def convert_to_yolo_format(yolo_results: Dict[str, Any], input_size: int) -> List[str]:
    """
    yolo로 detecting된 bbox를 yolo training용 format으로 변환하는 함수

    Args:
        yolo_results: label 정보와 bbox 정보가 담겨있는 딕셔너리
            {
                "0": {
                    "label": "3",
                    "bbox": [[left_top], [right_bottom]],
                    "conf": 0.713
                },
                ...
            }
        input_size: bbox 기준 이미지 사이즈

    Returns: 
        annotations: label 정보가 담겨있는 리스트
            [
                "{label} {x_center} {y_center} {width} {height}",
                ...
            ]
    """
    annotations = []

    for _, result in yolo_results.items():
        xmin, ymin = result['bbox'][0]
        xmax, ymax = result['bbox'][1]

        x_center = (xmin + xmax) / 2 / input_size
        y_center = (ymin + ymax) / 2 / input_size
        width = (xmax - xmin) / input_size
        height = (ymax - ymin) / input_size

        label = result['label'] if result['label'] != "" else "#"

        annotations.append(f"{label} {x_center:8f} {y_center:8f} {width:8f} {height:8f}\n")

    return annotations

###############################################################################################################
# 이미지 가공
###############################################################################################################
def correct_image_orientation(image: Image.Image) -> Image.Image:
    """
    이미지 회전 정보를 통해 정방향으로 조정하는 함수

    Args:
        image: PIL 이미지

    Returns: PIL 이미지
    """
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = dict(image._getexif().items())

        if exif[orientation] == 3:
            image = image.rotate(180, expand=True)
        elif exif[orientation] == 6:
            image = image.rotate(270, expand=True)
        elif exif[orientation] == 8:
            image = image.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError):
        pass
    return image



def get_quantile_results(results, top_percent=20, bottom_percent=20):
    # 결과를 DataFrame으로 변환
    df = pd.DataFrame.from_dict(results, orient='index')
    
    # 정확도의 상위/하위 기준 계산
    top_threshold = df['정확도'].quantile(1 - top_percent / 100)
    bottom_threshold = df['정확도'].quantile(bottom_percent / 100)
    
    # 상위 및 하위 결과 필터링
    top_results = df[df['정확도'] >= top_threshold].to_dict(orient='index')
    bottom_results = df[df['정확도'] <= bottom_threshold].to_dict(orient='index')
    return top_results, bottom_results

def resize_image(image_path):
    # 이미지 열기
    img = Image.open(image_path)
    
    # 세로 크기 고정 (48 픽셀), 가로 크기는 비율 유지
    target_height = 48
    width, height = img.size
    target_width = int(target_height * (width / height))
    
    # 이미지 크기 조정
    img = img.resize((target_width, target_height), Image.ANTIALIAS)
    return img


def visualize_ocr(image, boxes, txts, scores, font_path="/usr/share/fonts/truetype/nanum/NanumSquareEB.ttf", font_size=20, scoreless_mode=False):
    """
    Visualize OCR results with bounding boxes and text alignment.
    
    Args:
        image: PIL Image object
        boxes: List of bounding boxes [[[x1, y1], [x2, y2], [x3, y3], [x4, y4]], ...]
        txts: List of recognized texts corresponding to the bounding boxes
        scores: List of confidence scores corresponding to the texts
        font_path: Path to the font file supporting Korean characters
        font_size: Font size for the text
        scoreless_mode: If True, ignore score values (use blue color for all) and show bounding boxes only on the left image.
    """
    # Clone the original image for box drawing
    image_with_boxes = image.copy()
    draw = ImageDraw.Draw(image_with_boxes)

    # Load font
    try:
        font = ImageFont.truetype(font_path, size=font_size)
    except IOError:
        raise FileNotFoundError(f"Font not found at {font_path}. Please specify a valid font path.")

    # Define score-based colors (or force blue if scoreless_mode is True)
    def get_color(score):
        if scoreless_mode:
            return "blue"
        if score >= 0.8:
            return "green"  # High confidence
        elif score >= 0.5:
            return "orange"  # Medium confidence
        elif score > 0:
            return "red"  # Low confidence
        else:
            return "gray"

    # Draw bounding boxes and annotate with score on the image_with_boxes only if not in scoreless_mode
    for box, text, score in zip(boxes, txts, scores):
        box_tuple = [(x, y) for x, y in box]
        color = get_color(score)
        draw.polygon(box_tuple, outline=color, width=2)
        if not scoreless_mode:
            draw.text((box[0][0], box[0][1] - font_size), f"{score:.2f}", fill=color, font=font)

    # Create an empty canvas for aligned text (right image)
    aligned_image = Image.new('RGB', image.size, (255, 255, 255))
    draw_aligned = ImageDraw.Draw(aligned_image)

    for box, text, score in zip(boxes, txts, scores):
        x_coords = [point[0] for point in box]
        y_coords = [point[1] for point in box]
        center_x = sum(x_coords) / 4
        center_y = sum(y_coords) / 4

        color = get_color(score)
        draw_aligned.text((center_x, center_y), text, fill=color, font=font, anchor="mm")

    # Plot both images side by side
    fig, axes = plt.subplots(1, 2, figsize=(15, 10))
    axes[0].imshow(np.array(image_with_boxes))
    axes[0].set_title("Image with Bounding Boxes")
    axes[0].axis("off")

    axes[1].imshow(np.array(aligned_image))
    axes[1].set_title("Aligned Text")
    axes[1].axis("off")

    plt.tight_layout()
    plt.show()


def resize_bboxes(bboxes, original_size, new_size):
    W_original, H_original = original_size
    W_new, H_new = new_size

    # 크기 비율 계산
    x_scale = W_new / W_original
    y_scale = H_new / H_original

    # 모든 bbox 좌표 변환
    resized_bboxes = []
    for bbox in bboxes:
        resized_bbox = [[int(x * x_scale), int(y * y_scale)] for x, y in bbox]
        resized_bboxes.append(resized_bbox)

    return resized_bboxes



def convert_to_yolo_except_hashtag(ocr_data, img_width, img_height):
    yolo_labels = []
    for obj_id, obj in ocr_data.items():
        if obj["label"]=="#":
            pass
        else:
            bbox = obj["bbox"]
            x_min = min(p[0] for p in bbox)
            y_min = min(p[1] for p in bbox)
            x_max = max(p[0] for p in bbox)
            y_max = max(p[1] for p in bbox)
    
            # YOLO 형식 변환 (정규화)
            x_center = ((x_min + x_max) / 2) / img_width
            y_center = ((y_min + y_max) / 2) / img_height
            width = (x_max - x_min) / img_width
            height = (y_max - y_min) / img_height
    
            yolo_labels.append(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
    
    return "\n".join(yolo_labels)


def convert_yolo_dict_to_labels(yolo_dict, input_size, img_width, img_height):
    yolo_labels = []

    for item in yolo_dict.values():
        if item["label"] != 0:
            continue  # label이 0이 아닌 경우 무시

        x_min, y_min = item["bbox"][0]
        x_max, y_max = item["bbox"][1]

        # 리사이즈 된 1024x1024 기준에서 원본 크기로 변환
        x_min = (x_min / input_size) * img_width
        y_min = (y_min / input_size) * img_height
        x_max = (x_max / input_size) * img_width
        y_max = (y_max / input_size) * img_height

        # YOLO 형식으로 변환
        x_center = (x_min + x_max) / 2 / img_width
        y_center = (y_min + y_max) / 2 / img_height
        width = (x_max - x_min) / img_width
        height = (y_max - y_min) / img_height

        # YOLO 라벨 저장
        yolo_labels.append(f"1 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

    return yolo_labels


def yolo_to_bbox(yolo_labels, img_width, img_height):
    bboxes = []
    labels = []
    
    for line in yolo_labels:
        parts = line.strip().split()
        label, x_center, y_center, width, height = map(float, parts)

        # YOLO 좌표 -> 픽셀 좌표 변환
        x_center *= img_width
        y_center *= img_height
        width *= img_width
        height *= img_height

        # Bounding Box 좌표 계산
        x_min = x_center - (width / 2)
        y_min = y_center - (height / 2)
        x_max = x_center + (width / 2)
        y_max = y_center + (height / 2)

        # 4개의 꼭짓점 좌표로 변환
        bbox = [
            [x_min, y_min],  # 좌상단
            [x_max, y_min],  # 우상단
            [x_max, y_max],  # 우하단
            [x_min, y_max]   # 좌하단
        ]
        
        bboxes.append(bbox)
        labels.append(str(label))
    return bboxes, labels


def preprocess_roi(cropped, target_width=320, target_height=48):
    h, w = cropped.shape[:2]
    ratio = w / float(h)
    
    # 종횡비를 유지하면서 높이 맞추기
    if int(target_height * ratio) <= target_width:
        resized_w = int(target_height * ratio)
        resized = cv2.resize(cropped, (resized_w, target_height))
        
        # 패딩 추가
        processed = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        processed[:, 0:resized_w, :] = resized
    else:
        # 너비가 너무 길면 너비에 맞추고 높이 조정
        resized_h = int(target_width / ratio)
        resized = cv2.resize(cropped, (target_width, resized_h))
        
        # 패딩 추가 (세로 중앙 정렬)
        processed = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        pad_top = (target_height - resized_h) // 2
        processed[pad_top:pad_top+resized_h, :, :] = resized
    
    return processed
    
def process_image_batch(image_path, ocr, batch_size=32, width=320, height=48):
    # OpenCV로 이미지 로드 + RGB 변환 (빠른 처리)
    img_np = cv2.imread(image_path)
    if img_np is None:
        # OpenCV 실패시 PIL로 시도 (안정성)
        img = Image.open(image_path)
        img_np = np.array(img)
    else:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)

    # Detection 수행
    boxes_result = ocr.text_detector(img_np)
    boxes = boxes_result[0]

    # ROI 추출 및 전처리
    roi_images = []
    valid_boxes = []

    for points in boxes:
        x_min = int(min(points[:, 0]))
        x_max = int(max(points[:, 0]))
        y_min = int(min(points[:, 1]))
        y_max = int(max(points[:, 1]))
        
        # ROI 추출
        cropped = img_np[y_min:y_max, x_min:x_max]
        # processed = cv2.resize(cropped, (width, height))
        processed = preprocess_roi(cropped, width, height)
        
        roi_images.append(processed)
        valid_boxes.append(points)

    paddle_boxes = []
    paddle_txts = []
    paddle_scores = []

    # 배치 단위로 Recognition 수행
    for i in range(0, len(roi_images), batch_size):
        batch_images = roi_images[i:i+batch_size]
        batch_boxes = valid_boxes[i:i+batch_size]
        
        rec_results = ocr.text_recognizer(batch_images)
        
        if rec_results is None or len(rec_results[0]) == 0:
            continue
            
        texts = rec_results[0]
        
        for j, (text_info, box) in enumerate(zip(texts, batch_boxes)):
            if text_info is not None:
                text, conf = text_info
                paddle_boxes.append(box.tolist())
                paddle_txts.append(text)
                paddle_scores.append(conf)

    return paddle_boxes, paddle_txts, paddle_scores
