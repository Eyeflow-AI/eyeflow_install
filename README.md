# eyeflow_install
Eyeflow Scripts para instalação e setup

## Runtime
Primeiramente, instale o NVIDIA driver
On Ubuntu 22.04, you can install the NVIDIA driver with the following command:
 - ```sudo apt install -y nvidia-driver-550```

Na Azure VM, o NVIDIA driver é instalado com o comando:
 - ```sudo apt install -y ubuntu-drivers-common && sudo ubuntu-drivers autoinstall```

Instale o 'curl' para execução do script:
 - ```sudo apt update && sudo apt install curl```

Edge x86 execução local:
 - ```curl -sL https://github.com/Eyeflow-AI/eyeflow_install/releases/latest/download/setup_edge_x86-local.sh | sudo bash```

Edge x86 execução em container:
 - ```curl -sL https://github.com/Eyeflow-AI/eyeflow_install/releases/latest/download/setup_edge_x86-container.sh | sudo bash```

Edge Jetson:
 - ```curl -sL https://github.com/Eyeflow-AI/eyeflow_install/releases/latest/download/setup_edge_jetson.sh | sudo bash```

## Pos Instalação
Após a instalação, é necessário criar o device no Eyeflow.App para emissão da licença e associar um flow.

Instale a licença no device, informando o nome do Ambiente e do Device
 - ```python3 /opt/eyeflow/install/request_license.py```

Baixe o flow e os modelos para o device
 - ```python3 /opt/eyeflow/install/cloud_sync.py```

Instale o eyeflow_edge e componentes
 - ```python3 /opt/eyeflow/install/upgrade_edge --upgrade_eyeflow```

### Configuração da Edge Container:
Para que o edge possa acessar as câmeras são necessárias configurações específicas mapeando a rede ou as USBs do host para o container.
 Essas configurações devem ser atualizadas no ```/opt/eyeflow/install/compose.yaml```.

Ex: opções para acessar câmeras FLIR
```
--volume /opt/spinnaker:/opt/spinnaker \
--env FLIR_GENTL64_CTI=/opt/spinnaker/lib/flir-gentl/FLIR_GenTL.cti \
--device=/dev/bus/usb/002/002 \
```

Após a instalação deve-se ajustar os scripts ```/opt/eyeflow/install/start_edge``` e ```/opt/eyeflow/install/stop_edge``` para a configuração específica da máquina.
