from datetime import datetime
import uuid

class Task:
    def __init__(self, title, description="", priority="中", status="未完成", expected_time=None, tags=None, summary=None):
        self.id = str(uuid.uuid4())  # 生成唯一ID
        self.title = title
        self.description = description
        self.priority = priority
        self.status = status
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed_at = None
        self.expected_time = expected_time  # 预期完成时间（分钟）
        self.tags = tags or []  # 标签列表
        self.summary = summary  # 任务完成总结

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "expected_time": self.expected_time,
            "tags": self.tags,
            "summary": self.summary
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            data["title"], 
            data["description"], 
            data["priority"], 
            data["status"],
            data.get("expected_time"),
            data.get("tags", []),
            data.get("summary")
        )
        task.id = data.get("id", str(uuid.uuid4()))  # 如果没有ID，生成新的
        task.created_at = data["created_at"]
        task.completed_at = data["completed_at"]
        return task

    @staticmethod
    def format_time(seconds):
        """将秒数转换为 hh:mm:ss 格式"""
        if seconds is None:
            return "00:00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def get_expected_time_str(self):
        """获取预期时间的字符串表示（hh:mm:ss）"""
        if self.expected_time is None:
            return "00:00:00"
        return self.format_time(self.expected_time * 60)  # 转换分钟为秒

    def get_total_time_str(self, total_seconds=0):
        """获取总计时时间的字符串表示（hh:mm:ss）"""
        return self.format_time(total_seconds)

class FocusSession:
    def __init__(self, task_id, start_time=None):
        self.id = str(uuid.uuid4())
        self.task_id = task_id
        self.start_time = start_time or datetime.now()
        self.end_time = None
        self.duration = 0  # Duration in seconds
        self.abandoned = False  # 标记是否被放弃

    def end_session(self):
        self.end_time = datetime.now()
        # 确保duration计算正确，使用整数秒数
        self.duration = int((self.end_time - self.start_time).total_seconds())
        # 确保duration不为负数
        if self.duration < 0:
            self.duration = 0

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            "duration": self.duration,
            "abandoned": self.abandoned
        }

    @classmethod
    def from_dict(cls, data):
        session = cls(data["task_id"])
        session.id = data["id"]
        session.start_time = datetime.strptime(data["start_time"], "%Y-%m-%d %H:%M:%S")
        if data["end_time"]:
            session.end_time = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M:%S")
        session.duration = data["duration"]
        session.abandoned = data.get("abandoned", False)
        return session 
