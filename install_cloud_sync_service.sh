cp cloud_sync.service /etc/systemd/system/.
cp cloud_sync.timer /etc/systemd/system/.
systemctl enable cloud_sync.service
systemctl start cloud_sync.service
systemctl enable --now cloud_sync.timer
