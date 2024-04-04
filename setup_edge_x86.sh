echo "Edge installation started"

apt update
# apt upgrade -y

# wget
if [ $(dpkg-query -W -f='${Status}' wget 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  apt install -y curl wget
fi

# NVIDIA Driver
if [ $(dpkg-query -W -f='${Status}' nvidia-driver-* 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Please, install the NVIDIA driver first"
  echo "On Ubuntu 20.04, you can install the NVIDIA driver with the following command:"
  echo "sudo apt install nvidia-driver-535-server"
  echo
  echo "On Azure VM, you can install the NVIDIA driver with the following command:"
  echo "sudo apt install -y ubuntu-drivers-common && ubuntu-drivers autoinstall"
  echo
  echo "After installing the NVIDIA driver, please run this script again"
  exit 0
fi

# Docker
if ! which docker > /dev/null ;
then
  echo "Installing Docker"
  curl https://get.docker.com | sh \
    && systemctl --now enable docker
fi

# NVIDIA Container - online
if [ ! -f /etc/apt/sources.list.d/nvidia-container-toolkit.list ];
then
  echo "Installing NVIDIA container"
  distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
      && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
      && curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

  apt update
  apt-get install -y nvidia-container-toolkit

  # NVIDIA Container - offline
  # dpkg -i nvidia-container-toolkit-base_1.13.0-1_amd64.deb nvidia-container-toolkit_1.13.0-1_amd64.deb libnvidia-container1_1.13.0-1_amd64.deb libnvidia-container-tools_1.13.0-1_amd64.deb

  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi

# Docker image
echo "Pulling Edge docker image"
docker pull eyeflowai/eyeflow_edge-x86_64:latest

# alternative
# gunzip eyeflow_edge.tar.gz
# docker load -i eyeflow_edge.tar

# install python
if [ $(dpkg-query -W -f='${Status}' python3 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Installing Python libs"
  apt install -y python3 python3-pip
fi

# install python pip
if [ $(dpkg-query -W -f='${Status}' python3-pip 2>/dev/null | grep -c "ok installed") -eq 0 ];
then
  echo "Installing Python libs"
  apt install -y python3-pip

  python3 -m pip install -U pip
fi

# install python libs
if ! python3 -c "import eyeflow_sdk" &> /dev/null;
then
  python3 -m pip install -U eyeflow_sdk
fi

# Eyeflow folder & user
if ! id -u "eyeflow" >/dev/null 2>&1;
then
  echo 'Creating eyeflow user'
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

if [ ! -f /opt/eyeflow/install/update_edge ];
then
  echo "Download Eyeflow files"
  wget https://eyeflow.ai/static/media/edge_install.tar.gz -P /tmp
  tar -xzf /tmp/edge_install.tar.gz -C /opt/eyeflow/install

  cd /opt/eyeflow/install/
  chmod +x stop_edge
  chmod +x start_edge
  chmod +x update_edge.py
  chmod +x upload_extracts.py

  echo "Installing services"
  sh install_update_edge_service.sh

  cp eyeflow_conf.json /opt/eyeflow/run/.
  mv run_flow.sh /opt/eyeflow/run/.
  chmod +x /opt/eyeflow/run/run_flow.sh
fi

if [ ! -f /opt/eyeflow/run/edge.license ];
then
  echo "Generating license"
  python3 /opt/eyeflow/install/request_license.py
fi

python3 /opt/eyeflow/install/update_eyeflow_version.py
python3 /opt/eyeflow/install/update_edge.py

echo "Edge installation finished"
