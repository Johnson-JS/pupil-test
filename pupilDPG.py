import dearpygui.dearpygui as dpg
import paramiko
import subprocess
import time
import os
import threading

class KeyboardHandledPage:
    def __init__(self):
        self.active_widget = 0
        self.widgets = []

    def setup_focus_management(self):
        for widget in self.widgets:
            dpg.set_item_user_data(widget, {'on_enter': self.on_widget_focused})

    def change_focus(self, sender, app_data, direction):
        self.active_widget = (self.active_widget + direction) % len(self.widgets)
        dpg.focus_item(self.widgets[self.active_widget])

    def on_widget_focused(self, sender, app_data):
        self.active_widget = self.widgets.index(sender)

    def simulate_click(self, sender, app_data):
        dpg.call_item_callback(self.widgets[self.active_widget])

def run_external_program(command):
    if isinstance(command, list):
        process = subprocess.Popen(command)
    else:
        process = subprocess.Popen([command])
    process.wait()

def save_paths(sender, app_data, user_data):
    labrecorder_path = dpg.get_value("labrecorder_input")
    psychopy_path = dpg.get_value("psychopy_input")
    pythonw_path = dpg.get_value("pythonw_input")
    with open("config.txt", "w") as file:
        file.write(f"LabRecorder:{labrecorder_path}\nPsychoPy:{psychopy_path}\nPythonW:{pythonw_path}\n")
    dpg.hide_item("settings_window")

def get_pi_ip(ssh, script_path='/home/js/pupil/get_ip.sh', file_path='/home/js/pupil/ip.txt'):
    try:
        ssh.exec_command(f'bash {script_path}')
        time.sleep(1)
        stdin, stdout, stderr = ssh.exec_command(f'cat {file_path}')
        ip_address = stdout.read().decode().strip()
        return ip_address
    except Exception as e:
        print(f"Error: {e}")
        return None

def open_settings(sender, app_data, user_data):
    config = read_config()  
    if not dpg.does_item_exist("settings_window"):
        with dpg.window(tag="settings_window", label="Settings", width=400, height=250):
            dpg.add_input_text(tag="labrecorder_input", label="LabRecorder Path", default_value=config['labrecorder_path'])
            dpg.add_input_text(tag="psychopy_input", label="PsychoPy Path", default_value=config['psychopy_path'])
            dpg.add_input_text(tag="pythonw_input", label="PythonW Path", default_value=config['pythonw_path'])
            dpg.add_button(label="Save", callback=save_paths)
    else:
        dpg.set_value("labrecorder_input", config['labrecorder_path'])
        dpg.set_value("psychopy_input", config['psychopy_path'])
        dpg.set_value("pythonw_input", config['pythonw_path'])
        dpg.show_item("settings_window")

def read_config():
    paths = {'labrecorder_path': '', 'psychopy_path': '', 'pythonw_path': ''}
    if os.path.exists("config.txt"):
        with open("config.txt", "r") as file:
            for line in file:
                parts = line.strip().split(':', 1)
                if len(parts) == 2:
                    key, value = parts
                    key = key.strip()
                    value = value.strip()
                    if key == 'LabRecorder':
                        paths['labrecorder_path'] = value
                    elif key == 'PsychoPy':
                        paths['psychopy_path'] = value
                    elif key == 'PythonW':
                        paths['pythonw_path'] = value
    return paths

def run_on_pi(host, port, username, password, commands):

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=host, port=port, username=username, password=password)
    
    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(command)
        print(stdout.read().decode())
        err = stderr.read().decode()
        if err:
            print("ERROR:", err)
    
    ssh.close()

class StartPage(KeyboardHandledPage):
    def __init__(self):
        super().__init__()
        self.config = read_config()
        config = read_config()
        print("Loaded config:", config)
        with dpg.handler_registry():
            dpg.add_key_down_handler(dpg.mvKey_Down, callback=lambda s, a, u: self.change_focus(s, a, 1))
            dpg.add_key_down_handler(dpg.mvKey_Up, callback=lambda s, a, u: self.change_focus(s, a, -1))
            dpg.add_key_down_handler(dpg.mvKey_Return, callback=self.simulate_click)

        with dpg.handler_registry():
            dpg.add_key_down_handler(dpg.mvKey_Down, callback=lambda s, a, u: self.change_focus(s, a, 1))
            dpg.add_key_down_handler(dpg.mvKey_Up, callback=lambda s, a, u: self.change_focus(s, a, -1))
            dpg.add_key_down_handler(dpg.mvKey_Return, callback=self.simulate_click)

        with dpg.window(label="Control Panel", no_resize=True, no_move=True, no_scrollbar=True, no_collapse=True, menubar=False, pos=(200, 150), width=200, height=300):
            self.Settings = dpg.add_button(label="Settings", callback=open_settings, user_data=self.config, width=200, height=50)
            self.Camera = dpg.add_button(label="Start Camera", callback=self.streaming, width=200, height=50)
            self.Start = dpg.add_button(label="Start Recording", callback=self.record_start, width=200, height=50)
            self.Quit = dpg.add_button(label="Quit", callback=lambda: dpg.stop_dearpygui(), width=200, height=50)

            self.widgets = [self.Settings, self.Camera, self.Start, self.Quit]
            self.setup_focus_management()

    def streaming(self, sender, app_data):
        pi_ip = 'pi'
        ssh_port = 22
        username = 'js'
        password = 'jjj'
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(pi_ip, port=ssh_port, username=username, password=password)

        stdin, stdout, stderr = ssh.exec_command("sudo lsof -i :3333")
        output = stdout.readlines()
        if len(output) > 0:
            port_pid = output[0].split()[1]
            kill_command = f"sudo kill -9 {port_pid}"
            ssh.exec_command(kill_command)

        ip_address = get_pi_ip(ssh)
        command = f'libcamera-vid -t 0 --inline --listen -o tcp://{ip_address}:3333 --width 800 --height 450 --framerate 30'
        ssh.exec_command(command)
        cmd_command = f"ffplay tcp://{ip_address}:3333 -fflags nobuffer -flags low_delay -framedrop"
        subprocess.run(cmd_command, shell=True)

    def record_start(self, sender, app_data):
        labrecorder_path = self.config.get('labrecorder_path')
        psychopy_script_path = self.config.get('psychopy_path')
        pythonw_path = self.config.get('pythonw_path')

        if not labrecorder_path or not psychopy_script_path or not pythonw_path:
            print("Error: One or more paths are empty. Please check your configuration.")
            return

        labrecorder_command = labrecorder_path
        psychopy_command = [pythonw_path, psychopy_script_path]
        host = 'pi'  
        port = 22
        username = 'js'
        password = 'jjj'  
        pi_commands = [
            "source ~/lsl-env/bin/activate && python ~/pupil/pi-recorder.py"
        ]


        threads = [
            threading.Thread(target=run_external_program, args=(labrecorder_command,)),
            threading.Thread(target=run_external_program, args=(psychopy_command,))
        ]
        threads.append(threading.Thread(target=run_on_pi, args=(host, port, username, password, pi_commands)))

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        print("All programs have been started.")

if __name__ == '__main__':
    dpg.create_context()
    start_page = StartPage()
    dpg.create_viewport(title='Control Panel', width=700, height=500)
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()
