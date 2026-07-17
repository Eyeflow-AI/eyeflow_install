cp move_parts_files.service /etc/systemd/system/.
cp move_parts_files.timer /etc/systemd/system/.
systemctl enable move_parts_files.service
systemctl start move_parts_files.service
systemctl enable --now move_parts_files.timer
