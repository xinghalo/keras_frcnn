import os
import json

labels = []
ids = set()

for file in os.listdir('/Users/xingoo/PycharmProjects/keras_frcnn/data/meta/json'):


    if file.startswith('test_') or file.startswith('train_'):
        print(file)
        type = ''
        if file.startswith('test_pairs_'):
            type = file.split('test_pairs_')[-1].split('.')[0]
        if file.startswith('train_pairs_'):
            type = file.split('train_pairs_')[-1].split('.')[0]

        with open('/Users/xingoo/PycharmProjects/keras_frcnn/data/meta/json/' + file, 'r') as f:
            content = f.read()
            content = json.loads(content, encoding='utf-8')
            #{"photo": 4534, "product": 7419, "bbox": {"width": 120, "top": 172, "height": 358, "left": 134}}
            for c in content:
                photo = c['photo']
                bbox = c['bbox']
                x1 = bbox['left']
                y1 = bbox['top']
                w = bbox['width']
                h = bbox['height']
                x2 = x1+w
                y2 = y1+h

                labels.append(str(photo).zfill(9)+','+str(x1)+','+str(y1)+','+str(x2)+','+str(y2)+','+str(type))
                ids.add(str(photo).zfill(9))
print(len(labels))
with open('/Users/xingoo/PycharmProjects/keras_frcnn/data/wtbi_label.txt','w') as f:
    for label in labels:
        f.write(label+'\n')

with open('/Users/xingoo/PycharmProjects/keras_frcnn/data/validate_photo.txt','w') as f:
    for label in ids:
        f.write(label+'\n')