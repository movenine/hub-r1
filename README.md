# hub-r1
This project is an LED hub board produced using the Orange Pi LTS-R1 Plus board equipped with the rockchip series of Debian embedded Linux.
오픈 하드웨어인 오렌지파이 임베디드 리눅스 보드를 활용한 LED 유니트 특허시제품 개발 프로젝트 입니다.

---

## Project Overview
- 전체 LED미디어월 시스템은 다수의 Unit이 매트릭스 형태의 구성으로 되어 있으며, 아래 그림과 같은 네트워크로 구성됩니다.
그림에서와 같이 운영서버와 직접 연결되는 Unit이 서버 역할을 하고, 나머지 Unit은 클라이언트로써 cascade 방식으로 연결됩니다.
서버 Unit은 ip를 할당 받으며 운영서버와 Tcp/ip 소켓 통신을 하는 반면, 클라이언트 Unit은 MAC 어드레스 기반의 통신 규격을 따릅니다.

![네트워크구성](https://github.com/movenine/hub-r1/assets/57665081/6b3259cd-6ba6-41e0-a2c7-52cf27d35ed8)


- HUB 보드의 내부 소프트웨어 구조는 크게 이벤트 관리자, 장치제어 관리자, 데이터베이스로 구분되는데, 이벤트 관리자는 영상신호 감지 상태 및 소비전력 측정 값을 데이터베이스에 저장하는 역할을 수행하고, 장치제어 관리자는 장치를 판별하는 ID를 가지고 연결된 다수의 장치들과 통신하고 미리 정의된 프로토콜을 분석 및 그에 따라 처리하는 역할을 수행합니다. 데이터베이스는 파일로 생성되며 주기적으로 업데이트된 데이터 정보를 관리합니다.

![소프트웨어구성](https://github.com/movenine/hub-r1/assets/57665081/0a2395ac-86e4-4946-b3e3-86f36bce2f08)

---

## build
- C언어 기반의 디바이스 드라이버를 swig를 통해 Python 환경에서 사용이 가능하도록 사전에 [WiringOp-python](https://github.com/orangepi-xunlong/wiringOP-Python.git)를 참조하여 빌드한다.
- Python 라이브러리 설치

  `sudo apt-get install python3-netifaces `

  `sudo apt-get install python3-pandas`

  `sudo apt-get install zlib1g-dev`

  `pip3 install pyinstaller`

- 리눅스 어플리케이션 빌드

  어플리케이션(App)은 총 2가지로 task_monitoring과 task_network 파일로 구성되는데 pyinstaller 명령어를 통해 각각 빌드(build)한다.

  `pyinstaller -F src/task_network.py`

  `pyinstaller -F src/task_monitoring.py`




  
