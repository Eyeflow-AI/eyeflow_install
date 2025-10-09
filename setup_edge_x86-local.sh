echo "Edge installation started"

apt update
apt upgrade -y

# wget
if [ $(dpkg-query -W -f='${Status}' wget 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt install -y curl wget
fi

# NVIDIA Driver
if [ $(dpkg-query -W -f='${Status}' nvidia-driver-* 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Please, install the NVIDIA driver first"
  echo "On Ubuntu 22.04, you can install the NVIDIA driver with the following command:"
  echo "sudo apt install -y nvidia-driver-550-server"
  echo
  echo "On Azure VM, you can install the NVIDIA driver with the following command:"
  echo "sudo apt install -y ubuntu-drivers-common && ubuntu-drivers autoinstall"
  echo
  echo "After installing the NVIDIA driver and reboot, please run this script again"
  exit 0
fi

# NVIDIA Container - online
if [ ! -f /etc/apt/sources.list.d/cuda-ubuntu2204-x86_64.list ];
then
  echo "Installing NVIDIA CuDA Toolkit"
  wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
  dpkg -i cuda-keyring_1.1-1_all.deb
  apt update
  apt-get install -y cuda-toolkit-12-4
  apt-get install -y libcudnn libcudnn-dev
fi

# install python
if [ $(dpkg-query -W -f='${Status}' python3 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Installing Python libs"
  apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools
fi

# install python libs
if ! python3 -c "import eyeflow_sdk" &> /dev/null;
then
  python3 -m pip install -U eyeflow_sdk
  python3 -m pip install nvidia-pyindex
  python3 -m pip install \
    onnx_graphsurgeon \
    onnx \
    tensorrt==10.0.1 \
    tensorrt-cu12==10.0.1 \
    opencv_python
fi

# Eyeflow folder & user
if ! id -u "eyeflow" >/dev/null 2>&1;
then
  echo 'Creating eyeflow user'
  read -p 'Eyeflow user password: ' PASS
  adduser --quiet --disabled-password --shell /bin/bash --home /home/eyeflow --gecos "User" eyeflow
  echo "eyeflow:$PASS" | chpasswd

  usermod -a -G users eyeflow
  usermod -a -G docker eyeflow
fi

if [ ! -d /opt/eyeflow ];
then
  echo "Creating Eyeflow folders"

  mkdir -p /opt/eyeflow
  chown -R eyeflow:users /opt/eyeflow
  chmod 775 /opt/eyeflow
  chmod g+rwxs /opt/eyeflow

  mkdir -p /opt/eyeflow/data
  mkdir -p /opt/eyeflow/log
  mkdir -p /opt/eyeflow/run
  mkdir -p /opt/eyeflow/components
  mkdir -p /opt/eyeflow/install
fi

if [ ! -f /opt/eyeflow/install/cloud_sync.py ];
then
  echo "Download Eyeflow files"
  wget https://github.com/Eyeflow-AI/eyeflow_install/releases/latest/download/edge_install.tar.gz -P /tmp
  tar -xzf /tmp/edge_install.tar.gz -C /opt/eyeflow/install

  cd /opt/eyeflow/install/
  chmod +x cloud_sync.py
  chmod +x upload_extracts.py

  cp eyeflow_conf.json /opt/eyeflow/run/.
  mv run_flow.sh /opt/eyeflow/run/.
  mv run_flow_monitor.sh /opt/eyeflow/run/.
  chmod +x /opt/eyeflow/run/run_flow.sh

  gsettings set org.gnome.desktop.background picture-uri file:///opt/eyeflow/install/eyeflow-background.jpg
fi

echo "Edge installation finished"
