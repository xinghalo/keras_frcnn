import requests

IMG_PATH = '/data1/Users/xingoo/Desktop/images/'
print('begin')

lines = []

with open('photos/photos.txt','r') as f:
    lines = f.readlines()

total = str(len(lines))
for index, line in enumerate(lines):
    if index > -1:
        arr = line.strip('\n').split(',')
        id = arr[0]
        url = arr[1]
        post_prefix = url.split('/')[-1].split('?')[0].split('.')[-1]
        while True:
            try:
                r = requests.get(url, timeout=5)

                with open(IMG_PATH + id + '.' + post_prefix, 'wb') as f:
                    f.write(r.content)

                print('下载到图片:' + id + '.' + post_prefix)
                break
            except IOError as e:
                print('超时' + url)

        print(str(index) + "/" + total)