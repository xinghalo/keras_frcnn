import json
import requests
import os

URL = 'https://midway.51tiangou.com/product/listing/init.node?id='
IMG_PATH = '/Users/xingoo/Desktop/product_images/'

# 读取id
ids = []
categories = []
with open('/Users/xingoo/Desktop/listings.csv','r') as f:
    lines = f.read().split('\n')
    for line in lines:
        if line != '':
            arr = line.split(',')
            ids.append(arr[0])
            categories.append(arr[1])

print("获得"+str(len(ids))+"条数据")

# 下载图片
total = str(len(ids))
for index, id in enumerate(ids):
    if index > 4259:
        if not os.path.exists(IMG_PATH+'/'+categories[index]):
            os.mkdir(IMG_PATH+'/'+categories[index])

        resp = requests.get(URL+id, verify=False)
        url = json.loads(resp.text)['data'][0]['data']['imageUrl']
        r = requests.request('get', url)

        with open(IMG_PATH+'/'+categories[index]+'/'+id+'.jpg','wb') as f:
            f.write(r.content)
        f.close()

        print(str(index)+"/"+total)