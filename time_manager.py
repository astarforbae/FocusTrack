import json
import os
import time
import threading
import keyboard
from datetime import datetime, timedelta
from tabulate import tabulate
from colorama import init, Fore, Style
from wcwidth import wcswidth
import platform
if platform.system() == 'Windows':
    import winsound

# 初始化colorama
init()

class Task:
    def __init__(self, title, description="", priority="中", status="未完成", expected_time=None, tags=None):
        self.title = title
        self.description = description
        self.priority = priority
        self.status = status
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at = None
        self.total_time = 0  # 总计时时间（秒）
        self.timer_start = None  # 计时开始时间
        self.is_timing = False  # 是否正在计时
        self.timer_thread = None  # 计时线程
        self.stop_timer = False  # 停止计时标志
        self.expected_time = expected_time  # 预期完成时间（分钟）
        self.tags = tags or []  # 标签列表

    def to_dict(self):
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_time": self.total_time,
            "expected_time": self.expected_time,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            data["title"], 
            data["description"], 
            data["priority"], 
            data["status"],
            data.get("expected_time"),
            data.get("tags", [])
        )
        task.created_at = data["created_at"]
        task.completed_at = data["completed_at"]
        task.total_time = data.get("total_time", 0)
        return task

    def start_timer(self):
        if not self.is_timing:
            self.timer_start = time.time()
            self.is_timing = True
            self.stop_timer = False
            self.timer_thread = threading.Thread(target=self._timer_display)
            self.timer_thread.daemon = True
            self.timer_thread.start()
            return True
        return False

    def _timer_display(self):
        while not self.stop_timer:
            current_time = self.get_current_time()
            time_str = self.format_time(current_time)
            expected_str = ""
            if self.expected_time:
                expected_minutes = self.expected_time
                current_minutes = current_time / 60
                if current_minutes > expected_minutes:
                    expected_str = f" (超出预期 {int(current_minutes - expected_minutes)} 分钟)"
                else:
                    expected_str = f" (剩余 {int(expected_minutes - current_minutes)} 分钟)"
            print(f"\r当前任务：{self.title} - 耗时：{time_str}{expected_str} (按 'q' 结束计时)", end="", flush=True)
            time.sleep(1)

    def pause_timer(self):
        if self.is_timing:
            self.stop_timer = True
            if self.timer_thread:
                self.timer_thread.join()
            self.total_time += time.time() - self.timer_start
            self.timer_start = None
            self.is_timing = False
            print("\r" + " " * 80 + "\r", end="", flush=True)  # 清除当前行
            return True
        return False

    def get_current_time(self):
        if self.is_timing:
            return self.total_time + (time.time() - self.timer_start)
        return self.total_time

    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def auto_wrap(text, max_width):
    # 按显示宽度自动换行，兼容中英文
    lines = []
    line = ''
    width = 0
    for ch in str(text):
        w = wcswidth(ch)
        if width + w > max_width:
            lines.append(line)
            line = ch
            width = w
        else:
            line += ch
            width += w
    if line:
        lines.append(line)
    return '\n'.join(lines)

class TimeManager:
    def __init__(self):
        self.tasks = []
        self.data_file = "tasks.json"
        self.tasks_hash = None  # 添加哈希值用于检测更改
        self.load_tasks()

    def pad_str(self, s, width):
        s = str(s)
        pad = width - wcswidth(s.split('\n')[0])  # 只补第一行，防止多行错位
        return s + ' ' * (pad if pad > 0 else 0)

    def add_task(self, title, description="", priority="中", expected_time=None, tags=None):
        task = Task(title, description, priority, expected_time=expected_time, tags=tags)
        self.tasks.append(task)
        self.save_tasks()
        print(f"{Fore.GREEN}任务已添加：{title}{Style.RESET_ALL}")

    def list_tasks(self):
        if not self.tasks:
            print(f"{Fore.YELLOW}当前没有任务{Style.RESET_ALL}")
            return

        headers = ["序号", "标题", "描述", "优先级", "状态", "创建时间", "完成时间", "耗时", "预期时间", "标签"]
        table_data = []
        raw_data = []
        for i, task in enumerate(self.tasks, 1):
            priority_str = task.priority
            status_str = task.status
            # 对标题、描述、标签做自动换行
            title_str = auto_wrap(task.title, 20)
            desc_str = auto_wrap(task.description, 20)
            tags_str = auto_wrap(','.join(task.tags) if task.tags else '-', 20)
            time_str = task.format_time(task.get_current_time())
            if task.is_timing:
                time_str = f"{time_str} ⏱️"
            expected_time_str = f"{task.expected_time}分钟" if task.expected_time else "-"
            row = [
                i,
                title_str,
                desc_str,
                priority_str,
                status_str,
                task.created_at,
                task.completed_at or "-",
                time_str,
                expected_time_str,
                tags_str
            ]
            raw_data.append(row)
        # 计算每一列最大宽度
        col_widths = [max(wcswidth(str(x).split('\n')[0]) for x in col) for col in zip(headers, *raw_data)]
        # 补齐每一列
        for row in raw_data:
            table_data.append([self.pad_str(cell, col_widths[i]) for i, cell in enumerate(row)])
        headers_padded = [self.pad_str(h, col_widths[i]) for i, h in enumerate(headers)]
        print(tabulate(table_data, headers=headers_padded, tablefmt="grid", stralign="center", disable_numparse=True))

    def start_timer(self, task_index):
        if 1 <= task_index <= len(self.tasks):
            task = self.tasks[task_index - 1]
            if task.start_timer():
                print(f"\n{Fore.GREEN}开始计时任务：{task.title}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}输入 'q' 结束计时{Style.RESET_ALL}")
                
                # 使用线程来同时处理计时显示和输入
                def check_input():
                    while True:
                        if input().lower() == 'q':
                            self.pause_timer(task_index)
                            break
                
                input_thread = threading.Thread(target=check_input)
                input_thread.daemon = True
                input_thread.start()
            else:
                print(f"{Fore.YELLOW}任务已经在计时中{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}无效的任务序号{Style.RESET_ALL}")

    def pause_timer(self, task_index):
        if 1 <= task_index <= len(self.tasks):
            task = self.tasks[task_index - 1]
            if task.pause_timer():
                print(f"\n{Fore.GREEN}计时已结束：{task.title}{Style.RESET_ALL}")
                self.save_tasks()
            else:
                print(f"{Fore.YELLOW}任务未在计时中{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}无效的任务序号{Style.RESET_ALL}")

    def complete_task(self, task_index):
        if 1 <= task_index <= len(self.tasks):
            task = self.tasks[task_index - 1]
            if task.is_timing:
                task.pause_timer()
            task.status = "已完成"
            task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_tasks()
            print(f"{Fore.GREEN}任务已完成：{task.title}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}无效的任务序号{Style.RESET_ALL}")

    def delete_task(self, task_index):
        if 1 <= task_index <= len(self.tasks):
            task = self.tasks.pop(task_index - 1)
            self.save_tasks()
            print(f"{Fore.GREEN}任务已删除：{task.title}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}无效的任务序号{Style.RESET_ALL}")

    def save_tasks(self):
        # 生成当前任务数据的哈希值
        tasks_data = [task.to_dict() for task in self.tasks]
        current_hash = hash(json.dumps(tasks_data, sort_keys=True))
        
        # 只有当哈希值不同时（数据有变化）才写入文件
        if current_hash != self.tasks_hash:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            self.tasks_hash = current_hash

    def load_tasks(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in tasks_data]
                    # 初始化哈希值
                    self.tasks_hash = hash(json.dumps(tasks_data, sort_keys=True))
            except json.JSONDecodeError:
                print(f"{Fore.RED}任务数据文件损坏，创建新的任务列表{Style.RESET_ALL}")
                self.tasks = []
                self.tasks_hash = hash("[]")

    def countdown_timer(self, task_index, minutes=25):
        if 1 <= task_index <= len(self.tasks):
            task = self.tasks[task_index - 1]
            total_seconds = minutes * 60
            print(f"\n{Fore.GREEN}开始任务倒计时：{task.title}，共{minutes}分钟{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}输入 'q' 提前结束倒计时{Style.RESET_ALL}")
            remain_seconds = total_seconds
            last_display = -1
            start_time = time.time()
            
            # 使用线程来同时处理倒计时显示和输入
            def check_input():
                while True:
                    if input().lower() == 'q':
                        return True
                    time.sleep(0.1)
            
            input_thread = threading.Thread(target=check_input)
            input_thread.daemon = True
            input_thread.start()
            
            while remain_seconds > 0:
                # 实时刷新显示
                now = time.time()
                elapsed = int(now - start_time)
                if remain_seconds != total_seconds - elapsed:
                    remain_seconds = total_seconds - elapsed
                    if remain_seconds < 0:
                        remain_seconds = 0
                if remain_seconds != last_display:
                    mins, secs = divmod(remain_seconds, 60)
                    time_str = f"{mins:02d}:{secs:02d}"
                    print(f"\r剩余时间：{time_str} (输入 'q' 结束)", end="", flush=True)
                    last_display = remain_seconds
                
                # 检查输入线程是否结束
                if not input_thread.is_alive():
                    print(f"\n{Fore.YELLOW}倒计时已手动结束{Style.RESET_ALL}")
                    break
                    
                time.sleep(0.1)
            
            used_seconds = total_seconds - remain_seconds
            task.total_time += used_seconds
            self.save_tasks()
            if remain_seconds == 0:
                print(f"\n{Fore.GREEN}倒计时结束！{Style.RESET_ALL}")
                # 发出声音
                if platform.system() == 'Windows':
                    for _ in range(3):
                        winsound.Beep(1000, 500)
                        time.sleep(0.2)
                else:
                    print('\a')
        else:
            print(f"{Fore.RED}无效的任务序号{Style.RESET_ALL}")

def print_menu():
    print("\n=== 时间管理系统 ===")
    print("add        添加任务")
    print("list       查看任务列表")
    print("timer      开始计时")
    print("done       完成任务")
    print("delete     删除任务")
    print("countdown  开始倒计时 (25分钟)")
    print("exit       退出")
    print("================")

def main():
    manager = TimeManager()
    
    while True:
        print_menu()
        choice = input("请输入操作命令（如 add/list/timer/done/delete/countdown/exit）: ").strip().lower()
        
        if choice == "add":
            title = input("请输入任务标题: ")
            description = input("请输入任务描述 (可选): ")
            priority = input("请输入优先级 (高/中/低，默认中): ") or "中"
            expected_time = input("请输入预期完成时间（分钟，可选）: ")
            expected_time = int(expected_time) if expected_time.isdigit() else None
            tags = input("请输入标签（多个标签用逗号分隔，可选）: ")
            tags = [t.strip() for t in tags.split(',')] if tags else []
            manager.add_task(title, description, priority, expected_time, tags)
        
        elif choice == "list":
            manager.list_tasks()
        
        elif choice == "timer":
            manager.list_tasks()
            task_index = input("请输入要开始计时的任务序号: ")
            try:
                manager.start_timer(int(task_index))
            except ValueError:
                print(f"{Fore.RED}请输入有效的任务序号{Style.RESET_ALL}")
        
        elif choice == "done":
            manager.list_tasks()
            task_index = input("请输入要完成的任务序号: ")
            try:
                manager.complete_task(int(task_index))
            except ValueError:
                print(f"{Fore.RED}请输入有效的任务序号{Style.RESET_ALL}")
        
        elif choice == "delete":
            manager.list_tasks()
            task_index = input("请输入要删除的任务序号: ")
            try:
                manager.delete_task(int(task_index))
            except ValueError:
                print(f"{Fore.RED}请输入有效的任务序号{Style.RESET_ALL}")
        
        elif choice == "countdown":
            manager.list_tasks()
            task_index = input("请输入要倒计时的任务序号: ")
            try:
                minutes = input("请输入倒计时分钟数（回车默认25）: ")
                minutes = int(minutes) if minutes.isdigit() else 25
                manager.countdown_timer(int(task_index), minutes)
            except ValueError:
                print(f"{Fore.RED}请输入有效的任务序号{Style.RESET_ALL}")
        
        elif choice == "exit":
            print(f"{Fore.GREEN}感谢使用时间管理系统！{Style.RESET_ALL}")
            break
        
        else:
            print(f"{Fore.RED}无效的命令，请重试{Style.RESET_ALL}")

if __name__ == "__main__":
    main() 