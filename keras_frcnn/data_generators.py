from __future__ import absolute_import
import numpy as np
import cv2
import random
import copy
from . import data_augment
import threading
import itertools


def union(au, bu, area_intersection):
    area_a = (au[2] - au[0]) * (au[3] - au[1])
    area_b = (bu[2] - bu[0]) * (bu[3] - bu[1])
    area_union = area_a + area_b - area_intersection
    return area_union


def intersection(ai, bi):
    x = max(ai[0], bi[0])
    y = max(ai[1], bi[1])
    w = min(ai[2], bi[2]) - x
    h = min(ai[3], bi[3]) - y
    if w < 0 or h < 0:
        return 0
    return w * h


def iou(a, b):
    # a and b should be (x1,y1,x2,y2)

    if a[0] >= a[2] or a[1] >= a[3] or b[0] >= b[2] or b[1] >= b[3]:
        return 0.0

    area_i = intersection(a, b)
    area_u = union(a, b, area_i)

    return float(area_i) / float(area_u + 1e-6)


def get_new_img_size(width, height, img_min_side=600):
    """
    图片缩放到最大600像素，取宽度和高度里面最小的缩放到600
    :param width:
    :param height:
    :param img_min_side:
    :return:
    """
    if width <= height:
        f = float(img_min_side) / width
        resized_height = int(f * height)
        resized_width = img_min_side
    else:
        f = float(img_min_side) / height
        resized_width = int(f * width)
        resized_height = img_min_side

    return resized_width, resized_height


class SampleSelector:
    def __init__(self, class_count):
        # ignore classes that have zero samples
        self.classes = [b for b in class_count.keys() if class_count[b] > 0]
        self.class_cycle = itertools.cycle(self.classes)
        self.curr_class = next(self.class_cycle)

    def skip_sample_for_balanced_class(self, img_data):

        class_in_img = False

        for bbox in img_data['bboxes']:

            cls_name = bbox['class']

            if cls_name == self.curr_class:
                class_in_img = True
                self.curr_class = next(self.class_cycle)
                break

        if class_in_img:
            return False
        else:
            return True


def calc_rpn(C, img_data, width, height, resized_width, resized_height, img_length_calc_function):
    """
    计算RPN，首先获得特征图map的大小，然后挨个像素点遍历，反向生成原始图片的anchors
    遍历所有的Bbox,看这个anchor与哪个bbox的相交面积最大
    给每个bbox至少安排一个anchor与之相交


    :param C:
    :param img_data:
    :param width:
    :param height:
    :param resized_width:
    :param resized_height:
    :param img_length_calc_function:
    :return:
    """
    # 生成9个anchors
    downscale = float(C.rpn_stride)
    anchor_sizes = C.anchor_box_scales # [128, 256, 512]
    anchor_ratios = C.anchor_box_ratios # [[1, 1], [1, 2], [2, 1]]
    num_anchors = len(anchor_sizes) * len(anchor_ratios) # 9

    # calculate the output map size based on the network architecture
    # 这里的output_with和output_height应该是值特征Map的宽度和高度
    (output_width, output_height) = img_length_calc_function(resized_width, resized_height)

    n_anchratios = len(anchor_ratios)

    # initialise empty output objectives
    y_rpn_overlap = np.zeros((output_height, output_width, num_anchors))  # (h,w,n)
    y_is_box_valid = np.zeros((output_height, output_width, num_anchors)) # (h,w,n)
    y_rpn_regr = np.zeros((output_height, output_width, num_anchors * 4)) # (h,w,4*n)

    num_bboxes = len(img_data['bboxes']) # 图片中的bbox数量

    num_anchors_for_bbox = np.zeros(num_bboxes).astype(int)
    best_anchor_for_bbox = -1 * np.ones((num_bboxes, 4)).astype(int)    # [jy是特征图高度，ix是特征图宽度，anchor的形状，anchor的大小]
    best_iou_for_bbox = np.zeros(num_bboxes).astype(np.float32)         # [最大的相交面积]
    best_x_for_bbox = np.zeros((num_bboxes, 4)).astype(int)             # [x1, x2, y1, y2]
    best_dx_for_bbox = np.zeros((num_bboxes, 4)).astype(np.float32)     # [tx, ty, tw, th]

    # get the GT box coordinates, and resize to account for image resizing
    gta = np.zeros((num_bboxes, 4))
    for bbox_num, bbox in enumerate(img_data['bboxes']):
        # get the GT box coordinates, and resize to account for image resizing
        # 获得缩放后的边框位置
        gta[bbox_num, 0] = bbox['x1'] * (resized_width / float(width))
        gta[bbox_num, 1] = bbox['x2'] * (resized_width / float(width))
        gta[bbox_num, 2] = bbox['y1'] * (resized_height / float(height))
        gta[bbox_num, 3] = bbox['y2'] * (resized_height / float(height))

    # rpn ground truth

    for anchor_size_idx in range(len(anchor_sizes)):
        for anchor_ratio_idx in range(n_anchratios):
            # 循环遍历不同的尺寸和不同的形状
            anchor_x = anchor_sizes[anchor_size_idx] * anchor_ratios[anchor_ratio_idx][0]
            anchor_y = anchor_sizes[anchor_size_idx] * anchor_ratios[anchor_ratio_idx][1]

            for ix in range(output_width):
                # x-coordinates of the current anchor box
                x1_anc = downscale * (ix + 0.5) - anchor_x / 2
                x2_anc = downscale * (ix + 0.5) + anchor_x / 2

                # ignore boxes that go across image boundaries
                # 如果超出了边界，那么就忽略anchors
                if x1_anc < 0 or x2_anc > resized_width:
                    continue

                for jy in range(output_height):

                    # y-coordinates of the current anchor box
                    y1_anc = downscale * (jy + 0.5) - anchor_y / 2
                    y2_anc = downscale * (jy + 0.5) + anchor_y / 2

                    # ignore boxes that go across image boundaries
                    if y1_anc < 0 or y2_anc > resized_height:
                        continue

                    # bbox_type indicates whether an anchor should be a target
                    bbox_type = 'neg'

                    # this is the best IOU for the (x,y) coord and the current anchor
                    # note that this is different from the best IOU for a GT bbox
                    best_iou_for_loc = 0.0


                    # 计算当前的anchors和所有的bbox的iou信息
                    for bbox_num in range(num_bboxes):

                        # get IOU of the current GT box and the current anchor box
                        # 计算的是两个边框之间的相交面积
                        curr_iou = iou([gta[bbox_num, 0], gta[bbox_num, 2], gta[bbox_num, 1], gta[bbox_num, 3]],
                                       [x1_anc, y1_anc, x2_anc, y2_anc])
                        # calculate the regression targets if they will be needed
                        # 如果当前相交的面积最大，或者超过0.7，就保留起来
                        if curr_iou > best_iou_for_bbox[bbox_num] or curr_iou > C.rpn_max_overlap:
                            # cx,cy是边框bbox的中心点
                            cx = (gta[bbox_num, 0] + gta[bbox_num, 1]) / 2.0
                            cy = (gta[bbox_num, 2] + gta[bbox_num, 3]) / 2.0
                            # cxa,cya是anchor的中心点
                            cxa = (x1_anc + x2_anc) / 2.0
                            cya = (y1_anc + y2_anc) / 2.0

                            # 参考公式
                            tx = (cx - cxa) / (x2_anc - x1_anc)
                            ty = (cy - cya) / (y2_anc - y1_anc)
                            tw = np.log((gta[bbox_num, 1] - gta[bbox_num, 0]) / (x2_anc - x1_anc))
                            th = np.log((gta[bbox_num, 3] - gta[bbox_num, 2]) / (y2_anc - y1_anc))

                        if img_data['bboxes'][bbox_num]['class'] != 'bg':

                            # all GT boxes should be mapped to an anchor box, so we keep track of which anchor box was best
                            if curr_iou > best_iou_for_bbox[bbox_num]:
                                # [jy是特征图高度，ix是特征图宽度，anchor的形状，anchor的大小]
                                best_anchor_for_bbox[bbox_num] = [jy, ix, anchor_ratio_idx, anchor_size_idx]
                                # [最大的相交面积]
                                best_iou_for_bbox[bbox_num] = curr_iou
                                # [x1, x2, y1, y2]
                                best_x_for_bbox[bbox_num, :] = [x1_anc, x2_anc, y1_anc, y2_anc]
                                # [tx, ty, tw, th]
                                best_dx_for_bbox[bbox_num, :] = [tx, ty, tw, th]

                            # we set the anchor to positive if the IOU is >0.7 (it does not matter if there was another better box, it just indicates overlap)
                            if curr_iou > C.rpn_max_overlap:
                                bbox_type = 'pos'
                                num_anchors_for_bbox[bbox_num] += 1
                                # we update the regression layer target if this IOU is the best for the current (x,y) and anchor position
                                # 更新最好的iou和regr
                                if curr_iou > best_iou_for_loc:
                                    best_iou_for_loc = curr_iou
                                    best_regr = (tx, ty, tw, th)

                            # if the IOU is >0.3 and <0.7, it is ambiguous and no included in the objective
                            if C.rpn_min_overlap < curr_iou < C.rpn_max_overlap:
                                # gray zone between neg and pos
                                if bbox_type != 'pos':
                                    bbox_type = 'neutral'

                    # turn on or off outputs depending on IOUs
                    # 这里存储了特征图上的每个点对应的每个anchor的属性
                    # y_is_box_valid 1表示有效(包含了分类和bg几种情况)，0表示无效
                    # y_rpn_overlap 1表示大于0.7，0表示小于0.7
                    if bbox_type == 'neg':
                        y_is_box_valid[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 1
                        y_rpn_overlap[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 0
                    elif bbox_type == 'neutral':
                        y_is_box_valid[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 0
                        y_rpn_overlap[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 0
                    elif bbox_type == 'pos':
                        y_is_box_valid[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 1
                        y_rpn_overlap[jy, ix, anchor_ratio_idx + n_anchratios * anchor_size_idx] = 1
                        # 这个start是计算所有的anchor中，当前anchor的起始坐标
                        start = 4 * (anchor_ratio_idx + n_anchratios * anchor_size_idx)
                        # 每个特征图的点对应的回归系数
                        y_rpn_regr[jy, ix, start:start + 4] = best_regr

    # we ensure that every bbox has at least one positive RPN region
    # 如果某个bbox一个anchor都没有，那就挑一个最好的，至少保证每个bbox都有anchor与之对应
    for idx in range(num_anchors_for_bbox.shape[0]):
        if num_anchors_for_bbox[idx] == 0:
            # no box with an IOU greater than zero ...
            if best_anchor_for_bbox[idx, 0] == -1:
                continue
            y_is_box_valid[
                best_anchor_for_bbox[idx, 0], best_anchor_for_bbox[idx, 1],
                best_anchor_for_bbox[idx, 2] + n_anchratios *best_anchor_for_bbox[idx, 3]] = 1
            y_rpn_overlap[
                best_anchor_for_bbox[idx, 0], best_anchor_for_bbox[idx, 1],
                best_anchor_for_bbox[idx, 2] + n_anchratios *best_anchor_for_bbox[idx, 3]] = 1
            start = 4 * (best_anchor_for_bbox[idx, 2] + n_anchratios * best_anchor_for_bbox[idx, 3])
            y_rpn_regr[best_anchor_for_bbox[idx, 0], best_anchor_for_bbox[idx, 1], start:start + 4] = best_dx_for_bbox[idx, :]

    # 维度转换，之前是[h,w,anchor]，改成[anchor,h,w]
    y_rpn_overlap = np.transpose(y_rpn_overlap, (2, 0, 1))
    # 升维，之前是[anchor, h, w]，改成[1, anchor, h, w]
    y_rpn_overlap = np.expand_dims(y_rpn_overlap, axis=0)

    y_is_box_valid = np.transpose(y_is_box_valid, (2, 0, 1))
    y_is_box_valid = np.expand_dims(y_is_box_valid, axis=0)

    y_rpn_regr = np.transpose(y_rpn_regr, (2, 0, 1))
    y_rpn_regr = np.expand_dims(y_rpn_regr, axis=0)

    # 筛选overlap和valid都是1作为pos
    pos_locs = np.where(np.logical_and(y_rpn_overlap[0, :, :, :] == 1, y_is_box_valid[0, :, :, :] == 1))
    # 筛选overlap和valid一个是0，一个是1的，作为neg
    neg_locs = np.where(np.logical_and(y_rpn_overlap[0, :, :, :] == 0, y_is_box_valid[0, :, :, :] == 1))

    num_pos = len(pos_locs[0])

    # one issue is that the RPN has many more negative than positive regions, so we turn off some of the negative
    # regions. We also limit it to 256 regions.
    # 默认情况下负样本会有很多，这里对负样本做了筛选
    num_regions = 256
    # 保证正负样本总共只有256个
    if len(pos_locs[0]) > num_regions / 2:
        val_locs = random.sample(range(len(pos_locs[0])), len(pos_locs[0]) - num_regions / 2)
        y_is_box_valid[0, pos_locs[0][val_locs], pos_locs[1][val_locs], pos_locs[2][val_locs]] = 0
        num_pos = num_regions / 2

    if len(neg_locs[0]) + num_pos > num_regions:
        val_locs = random.sample(range(len(neg_locs[0])), len(neg_locs[0]) - num_pos)
        y_is_box_valid[0, neg_locs[0][val_locs], neg_locs[1][val_locs], neg_locs[2][val_locs]] = 0
    # 按照第二个维度的方向合并起来，这样y_rpn_cls的内容就是[1,18,38,54]
    # 第二个维度，前9个表示是否有效，后9个表示iou是否大于0.7
    y_rpn_cls = np.concatenate([y_is_box_valid, y_rpn_overlap], axis=1)
    # 前面36个是9个anchor重复4次的iou值是否大于0.7，后面36个是真正的边框回归系数
    # 总共是(1,72,38,50)的维度
    y_rpn_regr = np.concatenate([np.repeat(y_rpn_overlap, 4, axis=1), y_rpn_regr], axis=1)

    return np.copy(y_rpn_cls), np.copy(y_rpn_regr)


class threadsafe_iter:
    """Takes an iterator/generator and makes it thread-safe by
	serializing call to the `next` method of given iterator/generator.
	"""

    def __init__(self, it):
        self.it = it
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def next(self):
        with self.lock:
            return next(self.it)


def threadsafe_generator(f):
    """A decorator that takes a generator function and makes it thread-safe.
	"""

    def g(*a, **kw):
        return threadsafe_iter(f(*a, **kw))

    return g


def get_anchor_gt(all_img_data, class_count, C, img_length_calc_function, backend, mode='train'):
    # The following line is not useful with Python 3.5, it is kept for the legacy
    # all_img_data = sorted(all_img_data)

    sample_selector = SampleSelector(class_count)

    while True:
        if mode == 'train':
            random.shuffle(all_img_data)

        for img_data in all_img_data:
            try:

                if C.balanced_classes and sample_selector.skip_sample_for_balanced_class(img_data):
                    continue

                # read in image, and optionally add augmentation

                if mode == 'train':
                    # 训练集 图片可以进行翻转、旋转等操作
                    img_data_aug, x_img = data_augment.augment(img_data, C, augment=True)
                else:
                    # 测试集 不能改变图片
                    img_data_aug, x_img = data_augment.augment(img_data, C, augment=False)

                (width, height) = (img_data_aug['width'], img_data_aug['height'])
                (rows, cols, _) = x_img.shape

                assert cols == width
                assert rows == height

                # get image dimensions for resizing
                # 重新缩放图片，使得min(w,h)变成600
                (resized_width, resized_height) = get_new_img_size(width, height, C.im_size)

                # resize the image so that smalles side is length = 600px
                x_img = cv2.resize(x_img, (resized_width, resized_height), interpolation=cv2.INTER_CUBIC)

                try:
                    # y_rpn_cls 前9位表示是否有效，后9位表示是否大于0.7
                    # y_rpn_regr 前36位表示是否大于0.7，后36为是9个anchor扫描框
                    y_rpn_cls, y_rpn_regr = calc_rpn(C, img_data_aug, width, height, resized_width, resized_height,
                                                     img_length_calc_function)
                except:
                    continue

                # Zero-center by mean pixel, and preprocess image

                x_img = x_img[:, :, (2, 1, 0)]  # BGR -> RGB
                x_img = x_img.astype(np.float32)
                x_img[:, :, 0] -= C.img_channel_mean[0]
                x_img[:, :, 1] -= C.img_channel_mean[1]
                x_img[:, :, 2] -= C.img_channel_mean[2]
                x_img /= C.img_scaling_factor

                x_img = np.transpose(x_img, (2, 0, 1))
                x_img = np.expand_dims(x_img, axis=0)

                y_rpn_regr[:, y_rpn_regr.shape[1] // 2:, :, :] *= C.std_scaling

                if backend == 'tf':
                    x_img = np.transpose(x_img, (0, 2, 3, 1))
                    y_rpn_cls = np.transpose(y_rpn_cls, (0, 2, 3, 1))
                    y_rpn_regr = np.transpose(y_rpn_regr, (0, 2, 3, 1))

                yield np.copy(x_img), [np.copy(y_rpn_cls), np.copy(y_rpn_regr)], img_data_aug

            except Exception as e:
                print(e)
                continue
