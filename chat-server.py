import asyncio
import aiohttp
import json


class Color:

    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    TEAL = '\033[96m'
    END_COLOR = '\033[00m'

class User:

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.username = ''
        self.print_color = ''
        

class ChatServer:

    def __init__(self):
        self.users = []
        self.write_queue = asyncio.Queue()
        self.list_colors = [Color.TEAL, Color.RED, Color.GREEN,
                            Color.YELLOW, Color.BLUE, Color.PURPLE]
        self.type_last_color = 0


    def printColor(self, string, color):
        print(str('{} {}' + Color.END_COLOR).format(color, string))


    async def forward(self, user, message):
        # iterate over writer objects in self.writers list
        sender = user
        for user in self.users:
            if user != sender:
                if user.read_language:
                    message = await self.translate_message(message, user)

                await self.write_queue.put(user.writer.write(
                    f"{sender.print_color}{sender.username!r}: {message!r}{Color.END_COLOR}\n"
                .encode('utf-8')))


    async def announce(self, message):
        # announcements go to er body
        for user in self.users:
            await self.write_queue.put(user.writer.write(
                f"***{message!r}***\n"
            .encode('utf-8')))


    async def get_print_color(self):
        self.type_last_color = (self.type_last_color + 1) % len(self.list_colors)
        return self.list_colors[self.type_last_color] 


    async def create_user(self, reader, writer):
        user = User(reader, writer)
        user.writer.write(bytes
                          ('What username would you like to use? ','utf-8'))
        data = await user.reader.read(100)
        user.username = data.decode().strip()
        user.print_color = await self.get_print_color()
        self.users.append(user)
        await writer.drain()
        return user


    async def get_users(self, writer):
        user_list = []
        for user in self.users:
            user_list.append(user.username)
        message = f"Current users: {', '.join(user_list)!r}"
        writer.write(bytes(message + '\n', 'utf-8'))
        await writer.drain()


    async def client_check(self, user):
        message = bytes(
            'Press Enter to quit, or enter any other value to remain online: \n',
        'utf-8')
        user.writer.write(message)
        data = await user.reader.read(100)
        response = data.decode().strip()
        await user.writer.drain()
        return response


    async def detect_sentiment(self, user, message):
        sentiment_score = 0
        sentiment = ''
        detect_dict = {
            'text': message
        }
        async with aiohttp.ClientSession() as session:
            async with session.post('http://0.0.0.0:5000/detect-sentiment', data=detect_dict) as resp:
                sentiment_score_dict = await resp.json()
                sentiment_score_items = sentiment_score_dict.items()
                for key, value in sentiment_score_items:
                    if value > sentiment_score:
                        sentiment_score = value
                        sentiment = key

        user.writer.write(bytes(sentiment, 'utf-8'))
        await user.writer.drain()


    async def send_dm(self, user, message):
        try:
            sender = user
            for user in self.users:
                if f":{user.username}:" in message:
                    recipient = user
                    writer2 = user.writer

            message = message.replace('/dm', '')
            message = message.replace(f":{recipient.username}:", '').strip()       
            await self.write_queue.put(writer2.write(bytes
                                                     (f"**DM FROM {sender.username}: {message}\n", 'utf-8')))
            await writer2.drain()
        except Exception as e:
            print(str(e))


    async def handle(self, reader, writer):
        new_user = await self.create_user(reader, writer)
        message = f"{new_user.username} joined!"

        await self.write_queue.put(message)
        await self.announce(message)

        # set reader to listen for incoming messages
        while True:
            data = await new_user.reader.read(100)
            message = data.decode().strip()
            if message == "/users":
                await self.get_users(new_user.writer)
                continue

            # expose method for sending a DM
            if message.startswith('/dm'):
                await self.send_dm(new_user, message)
                continue

            # detect sentiment of message
            if message.startswith('/sentiment'):
                await self.detect_sentiment(new_user, message)
                continue

            # catch closed terminal bug
            if message == '':
                response = await self.client_check(new_user)
                if response == '':
                    break

            else:
                await self.forward(new_user, message)
            # call writer.drain() to write from [clear] the loops' buffer, 
            # and free up while you wait
            await writer.drain()

            # if client text == 'exit', break loop; 
            # stop reader from listening
            if message == "exit":
                message = f"{addr!r} wants to close the connection."
                print(message)
                await self.forward(writer, "Server", message)
                break

        # if reader is stopped, clean up by removing writer from list of writers
        self.users.remove(new_user)
        new_user.writer.close()


    async def main(self):
        # start server
        server = await asyncio.start_server(
            self.handle, '127.0.0.1', 8888)

        # alert admin that server is up
        addr = server.sockets[0].getsockname()
        self.printColor(f'Serving on {addr}', Color.TEAL)

        # use "async with" to clean up should the server be stopped abruptly
        async with server:
            await server.serve_forever()


if __name__ == '__main__':
    chat_server = ChatServer()
    asyncio.run(chat_server.main())