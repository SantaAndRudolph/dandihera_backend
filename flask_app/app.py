# 필요한 모듈 import
from flask import request, Flask, jsonify
from werkzeug.utils import secure_filename
from functools import wraps
import asyncio
from firebase_admin import credentials, storage, initialize_app, messaging
from firebase import firebase
import requests

cred = credentials.Certificate("/dandihera-key.json")
initialize_app(cred, {'storageBucket' : 'dandihera-f6f88.appspot.com'})

app = Flask(__name__)

firebase = firebase.FirebaseApplication('https://dandihera-f6f88-default-rtdb.asia-southeast1.firebasedatabase.app/', None)

def async_action(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapped

# detection 페이지
@app.route('/detect', methods=['POST'])
@async_action
async def detect():
    import os, shutil, numpy as np

    DATA_PATH = '/'
    SAVE_PATH = '/mobility/uploaded_file/' # 저장 경로

    # Yolo 모델 불러오기
    from ultralytics import YOLO
    model = YOLO(DATA_PATH + 'best_0.75.pt')

    if os.path.isdir(SAVE_PATH):
        shutil.rmtree(SAVE_PATH) # 비어있지 않으면 삭제
        shutil.rmtree(DATA_PATH + 'runs/detect/') # 하위 디렉토리 삭제
        os.mkdir(SAVE_PATH) # 새로 생성
        os.mkdir(DATA_PATH + 'runs/detect/') # 하위 디렉토리 생성
    else:
        os.mkdir(SAVE_PATH) # 폴더가 없으면 새로 생성
        os.mkdir(DATA_PATH + 'runs/detect/') # 하위 디렉토리 생성

    try:
        f = request.files['file']
        # 저장할 경로 + 파일명
        f.save(SAVE_PATH + secure_filename(f.filename))

        class_name_dict = {0: '정상', 1: '보행자도로 통행 위반', 2: '동승자 탑승 위반', 3: '안전모 미착용 위반', 4: '무단횡단 위반',
                           5: '횡단보도 주행 위반', 6: '신호 위반', 7: '정지선 위반'}
        # 결과 전달
        vio_list = []

        if '.mp4' not in f.filename and '.avi' not in f.filename and '.mov' not in f.filename:
            return 'not_correct_format'

        print(SAVE_PATH + f.filename)
        results = model.predict(source=SAVE_PATH + f.filename, save=True)
        video_pm_list = []

        for i in range(8):
            video_pm_list.append([i, 0])
            pm_dict = dict(video_pm_list)

        for result in results:
            # confidence가 0.6이상인 클래스만 저장하도록.
            uniq, cnt = np.unique(
                result.boxes.cls.cpu().numpy().astype(int)[np.where(result.boxes.conf.cpu().numpy() >= 0.6)],
                return_counts=True)  # Torch.Tensor -> numpy
            uniq_cnt_dict = dict(zip(uniq, cnt))
            for key in uniq_cnt_dict.keys():
                pm_dict[key] += uniq_cnt_dict[key]

        if sum(pm_dict.values()) > 0:
            for key, val in pm_dict.items():
                if val > 0 and key != 0:
                    vio_list.append(class_name_dict[key])
        else:
            vio_list.append('')

        # Firebase Realtime Database에 검출 정보 저장
        # vio_list
        new_data = {
            "VIO_TYPE" : vio_list,
            "VIO_DTM" : '20230820012100',
            "VIO_VIDEO" : f.filename,
            "VIO_ITEM" : 'Two-Wheel Vehicle Violation',
            "VIO_VEH_NUM" : '123가1234',
            "VIO_LOC" : {
                "LAT" : 38,
                "LON" : 38
            }
        }
        firebase.post('/VIO_INFO', new_data)

        # Firebase Cloud Storage에 원본 영상 저장
        bucket = storage.bucket()
        blob = bucket.blob(f.filename)
        blob.upload_from_filename(SAVE_PATH + f.filename)

        return vio_list
    except:
        return 'error'


@app.route('/info', methods=['GET'])
def getInfo():
      return firebase.get('/VIO_INFO', None)

@app.route('/notify', methods=['POST'])
def send_notification():
    data = request.json
    user_token = data['userToken']
    # Firebase Cloud Messaging URL
    FCM_URL = "https://fcm.googleapis.com/fcm/send"

    headers = {
        'Authorization': 'key=AAAAzvYle_I:APA91bFQtc1hA_IDgQvEuKg-hiEEnT2RfivvPjPRdvQGhFReoOyRLwy8Bdxavd-TG9ThjQ2CofubWXcnuNoR6nn9vSOWE5nxMo5K6Su-h4YIwgCq1MB4Ecd-KI9lAgeWBr0fWuteYbQ5',
        'Content-Type': 'application/json'
    }

    payload = {
        "to": user_token,
        "notification": {
            "title": "교통법규 위반 발생!",
            "body": "단디하라 앱에서 위반 사항을 손쉽게 신고하세요"
        }
    }

    response = requests.post(FCM_URL, json=payload, headers=headers)
    return jsonify(response.json()), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True)