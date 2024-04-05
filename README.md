# eyeflow_install
Eyeflow Scripts for setup and install

## Runtime
Install the NVIDIA driver first
On Ubuntu 20.04, you can install the NVIDIA driver with the following command:
 - ```sudo apt install nvidia-driver-535-server```

On Azure VM, you can install the NVIDIA driver with the following command:
 - ```sudo apt install -y ubuntu-drivers-common && sudo ubuntu-drivers autoinstall```

Para instalação da máquina Edge x86:
 - ```sudo apt update && sudo apt install curl```
 - ```curl -sL https://eyeflow.ai/static/media/setup_edge_x86.sh | sudo EDGE_ENVIRONMENT=<environment_name> EDGE_DEVICE=<device_name> PASS=<eyeflow user password>  bash```

Para instalação da máquina Edge Jetson:
 - ```sudo apt update && sudo apt install curl```
 - ```curl -sL https://eyeflow.ai/static/media/setup_edge_jetson.sh | sudo EDGE_ENVIRONMENT=<environment_name> EDGE_DEVICE=<device_name> PASS=<eyeflow user password> bash```

Antes de fazer o setup é necessário criar o device no Eyeflow.App para emissão da licença.

Para que o edge possa acessar as câmeras são necessárias configurações específicas mapeando a rede ou as USBs do host para o container.
 Essas configurações devem ser atualizadas no ```/opt/eyeflow/install/compose.yaml```.

Ex: opções para acessar câmeras FLIR
```
--volume /opt/spinnaker:/opt/spinnaker \
--env FLIR_GENTL64_CTI=/opt/spinnaker/lib/flir-gentl/FLIR_GenTL.cti \
--device=/dev/bus/usb/002/002 \
```

Após a instalação deve-se ajustar os scripts ```/opt/eyeflow/install/start_edge``` e ```/opt/eyeflow/install/stop_edge``` para a configuração específica da máquina.
