# YOLOv5 🚀 by Ultralytics, GPL-3.0 license
"""
Run inference on images, videos, directories, streams, etc.
Usage:
    $ python path/to/detect.py --source path/to/img.jpg --weights yolov5s.pt --img 640
"""
import argparse
import os
import sys

import warnings
from multiprocessing import Process, Pipe
from pathlib import Path

import numpy as np
import torch
import threading
import win32gui
from PIL import Image
from PyQt5.QtWidgets import QApplication

warnings.filterwarnings('ignore')
FILE = Path(__file__).resolve()
ROOT = FILE.parents[0]  # YOLOv5 root directory
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # add ROOT to PATH
ROOT = Path(os.path.relpath(ROOT, Path.cwd()))  # relative
app = QApplication(sys.argv)
desktop = QApplication.desktop()
# 获取显示器分辨率大小
screenRect = desktop.screenGeometry()
SCREEN_WIDTH = screenRect.width()
SCREEN_HEIGHT = screenRect.height()

SCREEN_WIDTH_3 = SCREEN_WIDTH // 3
SCREEN_HEIGHT_3 = SCREEN_HEIGHT // 3
SCREEN_HANDLE_NAME = 'Counter-Strike: Global Offensive - Direct3D 9'  # csgo
# SCREEN_HANDLE_NAME = '穿越火线'  # 穿越火线
from models.experimental import attempt_load
from utils.datasets import LoadcfImages
from utils.general import check_img_size, check_requirements, \
    increment_path, non_max_suppression, print_args, scale_coords, set_logging, \
    strip_optimizer
from utils.torch_utils import select_device


@torch.no_grad()
def run(weights=ROOT / 'yolov5s.pt',  # model.pt path(s)
        source=ROOT / 'data/images',  # file/dir/URL/glob, 0 for webcam
        imgsz=1000,  # inference size (pixels)
        conf_thres=0.25,  # confidence threshold
        iou_thres=0.45,  # NMS IOU threshold
        max_det=1000,  # maximum detections per image
        device='',  # cuda device, i.e. 0 or 0,1,2,3 or cpu
        view_img=False,  # show results
        save_crop=False,  # save cropped prediction boxes
        classes=None,  # filter by class: --class 0, or --class 0 2 3
        agnostic_nms=False,  # class-agnostic NMS
        augment=False,  # augmented inference
        visualize=False,  # visualize features
        update=False,  # update all models
        line_thickness=3,  # bounding box thickness (pixels)
        hide_labels=False,  # hide labels
        hide_conf=False,  # hide confidences
        half=False,  # use FP16 half-precision inference
        dnn=False,  # use OpenCV DNN for ONNX inference
        model=None,
        ):
    # Initialize
    set_logging()
    half &= device.type != 'cpu'  # half precision only supported on CUDA

    stride = int(model.stride.max())  # model stride
    names = model.module.names if hasattr(model, 'module') else model.names  # get class names

    if half:
        model.half()  # to FP16

    imgsz = check_img_size(imgsz, s=stride)  # check image size
    # Run inference
    if device.type != 'cpu':
        model(torch.zeros(1, 3, *imgsz).to(device).type_as(next(model.parameters())))  # run once

    dataset = LoadcfImages(source, img_size=imgsz, stride=stride, auto=True)

    for path, img, im0s, vid_cap in dataset:

        img = torch.from_numpy(img).to(device)
        img = img.half() if half else img.float()  # uint8 to fp16/32
        img = img / 255.0  # 0 - 255 to 0.0 - 1.0
        if len(img.shape) == 3:
            img = img[None]  # expand for batch dim

        # Inference
        visualize = increment_path('data/images' / Path(path).stem, mkdir=True) if visualize else False
        pred = model(img, augment=augment, visualize=visualize)[0]

        # NMS
        pred = non_max_suppression(pred, conf_thres, iou_thres, classes, agnostic_nms, max_det=max_det)
        # Process predictions
        results = []
        for i, det in enumerate(pred):  # per image

            p, s, im0, frame = path, '', im0s.copy(), getattr(dataset, 'frame', 0)
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

                # Write results

                for *xyxy, conf, cls in reversed(det):
                    xywh = torch.tensor(xyxy).view(1, 4).view(-1).tolist()
                    _x, _y, x_, y_ = xywh

                    results.append(((_x + x_) / 2, (_y + y_) / 2))
        return results

    if update:
        strip_optimizer(weights)  # update model (to fix SourceChangeWarning)


def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default=ROOT / 'runs/train/exp/weights/best.pt', help='model path(s)')
    parser.add_argument('--source', type=str, default=ROOT / 'data/images/screen.jpg', help='file/dir/URL/glob, 0 for webcam')
    parser.add_argument('--imgsz', '--img', '--img-size', nargs='+', type=int, default=[1024], help='inference size h,w')
    parser.add_argument('--conf-thres', type=float, default=0.25, help='confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU threshold')
    parser.add_argument('--max-det', type=int, default=1000, help='maximum detections per image')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--view-img', action='store_true', help='show results')
    parser.add_argument('--save-crop', action='store_true', help='save cropped prediction boxes')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --classes 0, or --classes 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')
    parser.add_argument('--visualize', action='store_true', help='visualize features')
    parser.add_argument('--line-thickness', default=3, type=int, help='bounding box thickness (pixels)')
    parser.add_argument('--hide-labels', default=False, action='store_true', help='hide labels')
    parser.add_argument('--hide-conf', default=True, action='store_true', help='hide confidences')
    parser.add_argument('--half', action='store_true', help='use FP16 half-precision inference')
    parser.add_argument('--dnn', action='store_true', help='use OpenCV DNN for ONNX inference')
    opt = parser.parse_args()
    opt.imgsz *= 2 if len(opt.imgsz) == 1 else 1  # expand
    print_args(FILE.stem, opt)
    return opt


def change_image_channels(image):
    # 4通道转3通道
    if image.mode == 'RGBA':
        r, g, b, a = image.split()
        image = Image.merge("RGB", (r, g, b))

    #  1 通道转3通道
    elif image.mode != 'RGB':
        image = image.convert("RGB")

    return image


# 写数据进程执行的代码:
def write(p1):
    print('Process(%s) write is writing...' % os.getpid())

    hwnd = win32gui.FindWindow(None, SCREEN_HANDLE_NAME)

    screen = QApplication.primaryScreen()
    # Load model

    # 只获取屏幕中心位置的截图
    while True:
        img = screen.grabWindow(hwnd, x=SCREEN_HEIGHT_3, y=SCREEN_HEIGHT_3, width=SCREEN_HEIGHT_3, height=SCREEN_HEIGHT_3).toImage()

        size = img.size()
        try:
            s = img.bits().asstring(size.width() * size.height() * img.depth() // 8)  # format 0xffRRGGBB
            arr = np.fromstring(s, dtype=np.uint8).reshape((size.height(), size.width(), img.depth() // 8))

            new_image = Image.fromarray(arr)
            new_image = change_image_channels(new_image)
            new_image = np.array(new_image)
            p1.send(new_image)

        except Exception as e:
            exit('游戏已退出')
            print('Error:', e)


def write_lug_cfg(results):
    file = 'E:/Project/private/Logitech-lua/cf/main.lua'
    msg = []
    for result in results:
        w = SCREEN_HEIGHT_3 + result[0]
        h = SCREEN_HEIGHT_3 + result[1]
        w = int(w / SCREEN_WIDTH * 65536)
        h = int(h / SCREEN_HEIGHT * 65536)

        msg.append(f'ReleaseMouseButton(1);\nMoveMouseRelative({w - 32768}, {h - 32768});\nPressMouseButton(1);\nPressMouseButton(1);')
    if msg:
        msg = '\nSleep(50);\n'.join(msg)
    else:
        msg = '\n'
    with open(file, 'w') as f:
        f.write(msg)


# 读数据进程执行的代码:
def read(c1):
    print('Process(%s) read1 is reading...' % os.getpid())
    opt = parse_opt()
    check_requirements(exclude=('tensorboard', 'thop'))
    device = select_device(0)
    model = attempt_load(opt.weights, map_location=device)
    opt.device = device
    opt.model = model
    while True:
        try:

            new_image = c1.recv()
            opt.source = [new_image]
            results = run(**vars(opt))
            # 起一个线程询lua脚本
            t = threading.Thread(target=write_lug_cfg, args=(results,))
            t.start()
            t.join()

        except Exception as e:
            c1.close()
            print('Error:', e)
            exit('窗口已关闭r1')


if __name__ == '__main__':
    # 父进程创建Queue，并传给各个子进程：
    p1, c1 = Pipe()
    reader = Process(target=read, args=(c1,))
    writer1 = Process(target=write, args=(p1,))
    # 启动子进程 reader1，读取:
    reader.start()
    # 启动子进程 writer，写入:
    writer1.start()

    # 等待 reader1 进程结束
    reader.join()
    # 等待 writer 结束:
    writer1.join()
