import pika


class QueueManager:
    def __init__(self, queue_name):
        self.queue_name = queue_name
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=queue_name)

    def send_message(self, message):
        self.channel.basic_publish(exchange='', routing_key=self.queue_name, body=message)

    def receive_message(self):
        method_frame, header_frame, body = self.channel.basic_get(queue=self.queue_name, auto_ack=True)
        if method_frame:
            return body.decode('utf-8')
        else:
            return None

    def close_connection(self):
        self.connection.close()
