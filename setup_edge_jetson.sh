echo "Edge installation started"

apt update
if [ $(dpkg-query -W -f='${Status}' rhythmbox 2>/dev/null | grep -c "ok installed") -eq 1 ];
then
  apt purge -y thunderbird* libreoffice* remmina* rhythmbox* aisleriot* gnome-mahjongg* gnome-mines* gnome-sudoku* gnome-todo* gnome-calendar* gnome-contacts* gnome-weather* gnome-maps* gnome-documents* gnome-photos* gnome-music*
fi

apt autoremove -y
apt upgrade -y

if [ $(dpkg-query -W -f='${Status}' nvidia-jetpack 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt install -y nvidia-jetpack
fi

if [ $(dpkg-query -W -f='${Status}' nano 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt install -y curl wget nano
fi

no | /usr/sbin/nvpmodel -m 0 2>/dev/null

if [ $(dpkg-query -W -f='${Status}' python3-pip 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Installing Python libs"
  apt-get install -y --no-install-recommends \
      libhdf5-dev \
      python3 \
      python3-pip \
      python3-dev \
      python3-setuptools \
      python3-libnvinfer

  python3 -m pip install -U pip
fi

# Eyeflow sdk
if ! python3 -c "import eyeflow_sdk" &> /dev/null;
then
  python3 -m pip install Cython
  python3 -m pip install nvidia-pyindex
  CUDA_HOME=/usr/local/cuda PATH=/usr/local/cuda/bin:$PATH LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH CUDA_INC_DIR=/usr/local/cuda/include python3 -m pip install pycuda
  python3 -m pip install \
      onnx_graphsurgeon \
      onnx \
      eyeflow_sdk
fi

# Eyeflow folder & user
if ! id -u "eyeflow" >/dev/null 2>&1;
then
  echo 'Creating eyeflow user'
  adduser --quiet --disabled-password --shell /bin/bash --home /home/eyeflow --gecos "User" eyeflow
  echo "eyeflow:$PASS" | chpasswd

  usermod -a -G users eyeflow
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
  chmod +x stop_edge
  chmod +x start_edge
  chmod +x cloud_sync.py
  chmod +x upload_extracts.py

  echo "Installing services"
  sh install_cloud_sync_service.sh

  cp eyeflow_conf.json /opt/eyeflow/run/.
  mv run_flow.sh /opt/eyeflow/run/.
  chmod +x /opt/eyeflow/run/run_flow.sh
fi

if [ ! -f /opt/eyeflow/run/edge.license ];
then
  echo "Generating license"
  python3 /opt/eyeflow/install/request_license.py
fi

python3 /opt/eyeflow/install/cloud_sync.py
python3 /opt/eyeflow/install/upgrade_edge --upgrade_eyeflow

echo "Edge installation finished"


# rm /home/eyeflow/Desktop/nv*
# gsettings set org.gnome.desktop.background picture-uri file:///opt/eyeflow/install/eyeflow-background.jpg