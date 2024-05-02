import cv2
import numpy as np
import pyautogui
import pydirectinput
import pyscreeze
import pygetwindow as gw
from PIL import Image
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import requests
import json
import threading
import subprocess

selected_images = {}
current_image_index = 0
detection_running = False
countdown_active = False
check_mouse_active = False

# ##################################################################
# sync Config
def load_config(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        return {}
    
def save_config(config, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(config, file, indent=4)

def update_config(key, value):
    config[key] = value
    save_config(config, config_filename)

config_filename = "config.json"  # ชื่อไฟล์ Config

config = load_config(config_filename)
if not config:
    config = {
        "debug": False,
        "account_name": "You Charactor Name",
        "key_you_need_to_press": 8,
        "On_line_notify": True,
        "line_notify_token": "insert Line Token here",
        "On_Discord_notify": True,
        "Discord_Webhook_url": "insert Discord Webhook here",
        "Config_log_message": "Message you need to notify",
        "ReLoop_When_First_Detected": True,
        "custom_resolution": False,
        "resolution_width": 1920,
        "resolution_height": 1080,
        "threshold": 0.8,
        "calibrate_image_mode": False,
        "MODE" : 1,
        "check_mouse_position": True,
        "mouse_point": [
            [158, 208],
            [1803, 175],
            [1596, 271],
            [1872, 268],
            [1060, 654]
        ]
    }
    save_config(config, config_filename)
# ##################################################################

def load_selected_images(folder_path):
    global selected_images
    image_files = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.jpeg', '.png', '.PNG'))]

    selected_images = {}
    for file_name in image_files:
        image_path = os.path.join(folder_path, file_name)
        img = cv2.imread(image_path, cv2.IMREAD_COLOR)
        selected_images[file_name] = img


def detect_selected_image():
    global selected_images, current_image_index
    focused_windows = gw.getWindowsWithTitle('NIGHT CROWS(1)')
    if not focused_windows:
        return False, None, None
    focused_window = focused_windows[0]

    window_left = focused_window.left
    window_top = focused_window.top
    window_width = focused_window.width
    window_height = focused_window.height

    region_width = window_width // 3
    region_height = window_height // 3
    region_left = window_left + window_width - region_width
    region_top = window_top + window_height - region_height

    screen = cv2.cvtColor(np.array(pyscreeze.screenshot(region=(region_left, region_top, region_width, region_height))), cv2.COLOR_RGB2BGR)
 
    current_image_name = list(selected_images.keys())[current_image_index]
    selected_image = selected_images[current_image_name]
    
    screen = cv2.GaussianBlur(screen, (3, 3), 0)
    selected_image = cv2.GaussianBlur(selected_image, (3, 3), 0)
    
    result = cv2.matchTemplate(screen, selected_image, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    
    threshold = config.get('threshold')
    
    if max_val > threshold:
        max_loc_global = (max_loc[0] + region_left, max_loc[1] + region_top)
        return True, current_image_name, max_loc_global
    
    return False, None, None
# ##################################################################
#  Check Mouse Position
def check_mouse_position():
    timestamp = datetime.now().strftime("%H:%M")
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    while check_mouse_active.is_set():
        if var.get():
            a = pyautogui.position()
            log_message = f"[ {timestamp} ] Mouse Position: {a} !\n"
            log_text.insert(tk.END, log_message, "green")
            log_text.delete("0.1", tk.END)
        else:
            log_text.delete("1.0", tk.END)

def on_checkbox_click():
    if detection_running == True:
        messagebox.showerror("Error", "Can't open when bot is activated")
    else:
        if var.get():
            check_mouse_active.set()
            threading.Thread(target=check_mouse_position).start()
        else:
            check_mouse_active.clear()

# ##################################################################
# Line Notify
line_notify_token = config.get("line_notify_token")

def _lineNotify(message, image_path=None):
    import requests
    url = 'https://notify-api.line.me/api/notify'
    headers = {'Authorization':'Bearer '+ line_notify_token}
    
    if image_path:
        files = {'imageFile': open(image_path, 'rb')}
        payload = {'message': message}
        response = requests.post(url, headers=headers, data=payload, files=files)
    else:
        payload = {'message': message}
        response = requests.post(url, headers=headers, data=payload)
    
    return response.status_code, response.content.decode('utf-8')

# ##################################################################
# Discord Webhook
Discord_Webhook_url = config.get("Discord_Webhook_url")

def send_discord_webhook(url, message, image_path):
    files = {
        'content': (None, message),
        'file': open(image_path, 'rb')
    }
    requests.post(url, files=files)
# ##################################################################

SCREENSHOT_WIDTH = 100
SCREENSHOT_HEIGHT = 100

def take_screenshot_at_location(location, save_path="detected_screenshot.png"):
    x, y = location
    
    top_left_x = x - SCREENSHOT_WIDTH // 2
    top_left_y = y - SCREENSHOT_HEIGHT // 2

    screen_width, screen_height = pyscreeze.screenshot().size
    top_left_x = max(0, top_left_x)
    top_left_y = max(0, top_left_y)
    
    actual_width = min(SCREENSHOT_WIDTH, screen_width - top_left_x)
    actual_height = min(SCREENSHOT_HEIGHT, screen_height - top_left_y)
    
    screenshot = pyscreeze.screenshot(region=(top_left_x, top_left_y, actual_width, actual_height))
    
    screenshot.save(save_path)
    print(f"Screenshot taken and saved to {save_path}")

    return save_path

delay = 5000

def start_detection(log_text, webhook_url):
    global current_image_index, detection_running, config
    config = load_config(config_filename)
    if not config:
        messagebox.showerror("Error", "Failed to load configuration. Please check the config.json file.")
        return
    detection_running = True
    timestamp = datetime.now().strftime("%H:%M")
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    log_message = f"[ {timestamp} ] Program Activate in mode [{config.get('MODE')}] !\n"
    log_text.insert(tk.END, log_message, "green")

    # ----------- Line Notify ---------------------
    if config.get('On_line_notify'):
        log_message = f"[ {timestamp} ] Enable Line Notify!\n"
        log_text.insert(tk.END, log_message, "green")
    else:
        log_message = f"[ {timestamp} ] Disable Line Notify!\n"
        log_text.insert(tk.END, log_message, "red")
    # ----------- Discord Notify ---------------------
    if config.get('On_Discord_notify'):
        log_message = f"[ {timestamp} ] Enable Discord Notify!\n"
        log_text.insert(tk.END, log_message, "green")
    else:
        log_message = f"[ {timestamp} ] Disable Discord Notify!\n"
        log_text.insert(tk.END, log_message, "red")
    # --------------------------------------------------
        
    log_message = f"[ {timestamp} ] Account Name : {config.get('account_name')}\n"
    log_text.insert(tk.END, log_message)
    while detection_running:
        found, image_name, location = detect_selected_image()

        if found:
            if config.get('debug'):
                log_message = f"Detected '{image_name}' at location {location}\n"
                log_text.insert(tk.END, log_message, "green")
                
                with open("detected_points.json", "a") as file:
                    json.dump({"image": image_name, "location": location}, file)
                    file.write("\n")

                screenshot_path = take_screenshot_at_location(location, "detected_screenshot.png")
                log_message = f"Screenshot saved at: {screenshot_path}\n"
                log_text.insert(tk.END, log_message, "green")

            timestamp = datetime.now().strftime("%H:%M")
            log_message = f"[ {timestamp} ] Account Name : {config.get('account_name')}\n[ {timestamp} ] Notify : {config.get('Config_log_message')}\n"
            log_text.insert(tk.END, log_message)
            log_text.yview(tk.END)

            focused_windows = gw.getWindowsWithTitle('NIGHT CROWS(1)')

            if focused_windows:
                try:
                    focused_window = focused_windows[0]
                    focused_window.minimize()
                    time.sleep(0.5)
                    focused_window.restore()
                    time.sleep(0.5)
                except Exception as e:
                    log_message = f"[ {timestamp} ] Error activating window: {e}\n"
                    log_text.insert(tk.END, log_message, "red")
            else:
                log_message = f"[ {timestamp} ] Window not found.\n"
                log_text.insert(tk.END, log_message, "red")

            screenshot = pyscreeze.screenshot(region=(focused_window.left, focused_window.top, focused_window.width, focused_window.height))
            resized_screenshot = screenshot.resize((854, 480), Image.LANCZOS)
            # resized_screenshot = screenshot.resize((2560, 1440), Image.LANCZOS)
            image_path = "screenshot.png"
            resized_screenshot.save(image_path)

            if config.get('On_line_notify'):
                status_code, response_content = _lineNotify(log_message, image_path)
                if status_code == 200:
                    log_text.insert(tk.END, f"[ {timestamp} ] Success Send Line Notification\n", "green")
                else:
                    log_text.insert(tk.END, f"[ {timestamp} ] Error To Send Line Notification\n", "red")
                    log_text.insert(tk.END, f"[ {timestamp} ] Status Code: {status_code}\n", "red")
                    log_text.insert(tk.END, f"[ {timestamp} ] Response Content: {response_content}\n", "red")

            if config.get('On_Discord_notify'):
                log_text.insert(tk.END, f"[ {timestamp} ] Success Send Discord Notification\n", "green")
                send_discord_webhook(webhook_url, log_message, image_path)
            
            os.remove(image_path)

            if config.get('MODE') == 1:
                pydirectinput.keyDown(f"{config.get('key_you_need_to_press')}")
                time.sleep(0.05)
                pydirectinput.keyUp(f"{config.get('key_you_need_to_press')}")
            elif config.get('MODE') == 2:
                focused_windows = gw.getWindowsWithTitle('NIGHT CROWS(1)')
                if focused_windows:
                    focused_window = focused_windows[0]
                    window_left = focused_window.left
                    window_top = focused_window.top
                    window_width = focused_window.width
                    window_height = focused_window.height

                    target_coordinates_relative = config.get('mouse_point')

                    scale_x = window_width / config.get('resolution_width')
                    scale_y = window_height / config.get('resolution_height')

                    for x_rel, y_rel in target_coordinates_relative:
                        absolute_x = window_left + int(x_rel * scale_x)
                        absolute_y = window_top + int(y_rel * scale_y)
                        pydirectinput.click(absolute_x, absolute_y)
                        time.sleep(1)

            current_image_index = (current_image_index + 1) % len(selected_images)

            if config.get('ReLoop_When_First_Detected'):
                log_message = f"[ {timestamp} ] Program Continue Detected !\n"
                log_text.insert(tk.END, log_message, "green")
            else:
                log_message = f"[ {timestamp} ] Stopping Program !\n"
                log_text.insert(tk.END, log_message, "red")
                break

        else:
            current_image_index = (current_image_index + 1) % len(selected_images)

        root.update_idletasks()
        root.update()
        cv2.waitKey(0)


def stop_detection_Button():
    global detection_running
    detection_running = False
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    timestamp = datetime.now().strftime("%H:%M")
    log_message = f"[ {timestamp} ] Stopping Program.\n"
    log_text.insert(tk.END, log_message, "red")
    log_text.yview(tk.END)
    

def select_folder_path():
    if detection_running == True:
        messagebox.showerror("Error", "Can't open when bot is activated")
    else:
        folder_path = filedialog.askdirectory()
        if folder_path:
            folder_path_entry.delete(0, tk.END)
        folder_path_entry.insert(0, folder_path)
        load_selected_images(folder_path)

def auto_select_folder_path(folder_path_entry, log_text):
    script_directory = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(script_directory, "image")
    log_text.tag_config("green", foreground="green")
    log_text.tag_config("red", foreground="red")
    if os.path.exists(folder_path):
        folder_path_entry.insert(0, folder_path)
        load_selected_images(folder_path)
    else:
        folder_path_entry.insert(0, 'ERROR')
        log_message = f" Error: 'image' folder not found in the script directory\n Plese Contact : Admin\n"
        log_text.insert(tk.END, log_message, "red")
        log_text.yview(tk.END)

def open_auto_select_path():
    folder_path = folder_path_entry.get()
    if detection_running == True:
        messagebox.showerror("Error", "Can't open when bot is activated")
    else:
        if os.path.isdir(folder_path):
            os.startfile(folder_path)
        else:
            messagebox.showerror("Error", "Invalid folder path!")

def open_config_file():
    if detection_running == True:
        messagebox.showerror("Error", "Can't open when bot is activated")
    else:
        try:
            subprocess.Popen(['notepad.exe', 'config.json'], shell=True)  
        except Exception as e:
            print("Error:", e)

def convert_images():
    new_sizes = [
        (43, 50),
        (29, 33),
        (19, 22),
        (172, 200),
        (115, 133),
        (86, 100),
        (36, 42),
        (36, 42),
        (28, 33),
        (22, 26),
        (50, 59),
        (57, 67),
        (73, 86),
        (43, 53),
        (32, 39),
        (38, 47),
        (31, 36),
        (36, 42),
        (46, 53)
    ]
    if config.get('calibrate_image_mode'):
        if detection_running == True:
            messagebox.showerror("Error", "Can't calibrate when bot is activated")
        else:
            file_path = filedialog.askopenfilename(initialdir=folder_path_entry.get())
            if file_path:
                original_image = Image.open(file_path)
                file_name, file_extension = os.path.splitext(file_path)
                for i, new_size in enumerate(new_sizes):
                    new_image = original_image.copy()
                    new_image = new_image.resize(new_size)
                    new_file_path = f"{file_name}_{new_size[0]}x{new_size[1]}_{i+1}{file_extension}"
                    new_image.save(new_file_path)
                    messagebox.showinfo("Success", "Calibrate Success")
                    break

def center_window(window, width, height):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()

    x = (screen_width - width) // 2
    y = (screen_height - height) // 2

    window.geometry(f"{width}x{height}+{x}+{y}")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Night Crows Auto Teleport")
    root.iconbitmap("icon.ico")
    window_width = 550
    window_height = 600
    center_window(root, window_width, window_height)

    folder_path_label = tk.Label(root, text="Database Image Folder")
    folder_path_label.pack(pady=5)

    folder_path_frame = tk.Frame(root)
    folder_path_frame.pack(pady=5)

    folder_path_entry = tk.Entry(folder_path_frame, width=40)
    folder_path_entry.pack(side=tk.LEFT, padx=5)

    button_entry_frame = tk.Frame(root)
    button_entry_frame.pack(pady=5)

    line_Token_label = tk.Label(root, text="Line Token is : ")
    line_Token_label.pack(pady=5)

    line_Default_text = tk.StringVar()
    line_Default_text.set(f"{line_notify_token}")

    line_Token_entry = tk.Entry(root, textvariable= line_Default_text , width=40, state='readonly')
    line_Token_entry.pack(padx=5)

    webhook_label = tk.Label(root, text="Discord Webhook URL:")
    webhook_label.pack(pady=5)

    webhook_Default_text = tk.StringVar()
    webhook_Default_text.set(f"{Discord_Webhook_url}")

    webhook_entry = tk.Entry(root, textvariable= webhook_Default_text , width=40, state='readonly')
    webhook_entry.pack(pady=3)

    select_folder_button = tk.Button(button_entry_frame, text="Select Image Folder", command=select_folder_path)
    select_folder_button.pack(side=tk.RIGHT, padx=5)

    load_folder_button = tk.Button(button_entry_frame, text="Open Image Folder", command=open_auto_select_path)
    load_folder_button.pack(side=tk.LEFT,padx=5)
    if config.get('calibrate_image_mode'):
        convert_button = tk.Button(button_entry_frame, text="Calibrate Image", command=convert_images)
        convert_button.pack(side=tk.LEFT,padx=5)

    if config.get('check_mouse_position'):
        var = tk.BooleanVar()
        checkmouse_button = tk.Checkbutton(root, text="Check Mouse Position", variable=var, command=on_checkbox_click)
        checkmouse_button.pack()
        check_mouse_active = threading.Event()

    button_frame = tk.Frame(root)
    button_frame.pack(pady=5)

    start_button = tk.Button(button_frame, text="Start Program", command=lambda: start_detection(log_text, webhook_entry.get()))
    start_button.pack(side=tk.RIGHT,padx=10)

    stop_button = tk.Button(button_frame, text="Stop Program", command=stop_detection_Button)
    stop_button.pack(side=tk.LEFT,padx=10)

    log_frame = tk.Frame(root)
    log_frame.pack(pady=10)

    log_text = tk.Text(log_frame, height=17, width=65)
    log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scrollbar = tk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    log_text.config(yscrollcommand=scrollbar.set)

    lower_frame = tk.Frame(root)
    lower_frame.pack(pady=5)

    open_config_button = tk.Button(lower_frame, text="Open Config Setting", command=open_config_file)
    open_config_button.pack(side=tk.LEFT,padx=10)

    auto_select_folder_path(folder_path_entry, log_text)

    root.mainloop()
