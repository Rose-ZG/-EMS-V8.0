import smtplib
import time
import cv2
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.header import Header

class EmailNotifier:
    def __init__(self, smtp_config):
        """
        smtp_config: dict 包含 server, port, user, password
        """
        self.config = smtp_config

    def send_fall_alert(self, receiver_email, frame, location="客厅"):
        """发送包含截帧的告警邮件"""
        if not receiver_email:
            return False

        # 1. 准备邮件对象
        msg = MIMEMultipart()
        current_time = time.strftime('%Y-%m-%d %H:%M:%S')
        msg['Subject'] = Header(f"【紧急警报】监测到老人跌倒 - {current_time}", 'utf-8')
        # 必须严格符合之前测试成功的 From 格式防止 550 错误
        msg['From'] = f"ElderMonitorSystem <{self.config['user']}>"
        msg['To'] = receiver_email

        # 2. 邮件正文
        body = f"""
                <html>
                <body>
                    <h2 style="color: #d9534f;">⚠️ 监测到跌倒异常</h2>
                    <p><b>告警时间：</b>{current_time}</p>
                    <p><b>发生地点：</b>{location}</p>
                    <p><b>系统状态：</b>已通过多帧确认逻辑验证，确认为真实跌倒或求助。</p>
                    <p>请立即查看下方现场抓拍图：</p>
                    <img src="cid:fall_image" style="width: 600px; border: 2px solid #333;">
                </body>
                </html>
                """
        msg.attach(MIMEText(body, 'html', 'utf-8'))

        # 3. 处理图片截帧
        try:
            # 将 OpenCV 的 BGR 图像转换为 JPG 格式
            _, buffer = cv2.imencode('.jpg', frame)
            image_data = buffer.tobytes()
            img_mime = MIMEImage(image_data)
            img_mime.add_header('Content-ID', '<fall_image>')
            img_mime.add_header('Content-Disposition', 'attachment', filename=f"fall_{int(time.time())}.jpg")
            msg.attach(img_mime)
        except Exception as e:
            print(f"[SMTP] 图片处理失败: {e}")

        # 4. 执行发送
        try:
            server = smtplib.SMTP_SSL(self.config['server'], self.config['port'], timeout=15)
            server.login(self.config['user'], self.config['password'])
            server.sendmail(self.config['user'], [receiver_email], msg.as_string())
            server.quit()
            print(f"[SMTP] Alert email sent to: {receiver_email}")
            return True
        except Exception as e:
            print(f"[SMTP] 邮件发送失败: {e}")
            return False