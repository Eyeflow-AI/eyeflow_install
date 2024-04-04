cp update_edge.service /etc/systemd/system/.
cp update_edge.timer /etc/systemd/system/.
systemctl enable update_edge.service
systemctl start update_edge.service
systemctl enable --now update_edge.timer
