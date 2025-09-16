sudo cp move_parts_files.timer /etc/systemd/system/.
sudo cp move_parts_files.service /etc/systemd/system/.
sudo cp purge_old_files.timer /etc/systemd/system/.
sudo cp purge_old_files.service /etc/systemd/system/.
sudo systemctl enable --now move_parts_files.service
sudo systemctl enable --now move_parts_files.timer
sudo systemctl enable --now purge_old_files.service
sudo systemctl enable --now purge_old_files.timer
