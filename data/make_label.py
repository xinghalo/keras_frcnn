import os
import cv2
from decimal import Decimal
PATH = '/Users/xingoo/Desktop/'

labels = []

for category in os.listdir(PATH+'labels/'):
    #print(category)
    if category != '.DS_Store':
        for product in os.listdir(PATH+'labels/'+category):
            #print(product)
            with open(PATH+'labels/'+category+'/'+product) as f:
                lines = f.readlines()
                if len(lines) > 1:
                    #print(lines[1].strip())
                    x1,y1,x2,y2 = lines[1].strip().split(' ')
                    image_path = PATH+'images_v2/'+category+'/'+(product.split('.')[0]+'.jpg')
                    img = cv2.imread(image_path)
                    h,w,_ = img.shape
                    #print(h)
                    #print(w)
                    labels.append(image_path
                                  +','+str(round(Decimal(w)*Decimal(x1),2))
                                  +','+str(round(Decimal(h)*Decimal(y1),2))
                                  +','+str(round(Decimal(w)*Decimal(x2),2))
                                  +','+str(round(Decimal(h)*Decimal(y2),2))
                                  +','+category)

for line in labels:
    print(line)

with open('/Users/xingoo/PycharmProjects/keras_frcnn/my_label_v2.txt','w',encoding='utf-8') as f:
    for line in labels:
        f.write(line+'\n')