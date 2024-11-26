import logging
import re
import asyncio
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, PeerChannel, PeerChat, PeerUser
import pytz
from datetime import datetime
import speedtest  # Menambahkan import untuk speedtest-cli

# String session yang telah Anda simpan
string_session = '1BVtsOH0Bu2hB73LTrUYcRyrrw7UgpAA8J8ajXNbt92Bc5rJP1csb1E20URERMkvkDKQhPmIhX0UtN0Z9OZN7C8wa0FSgwGCaYHDjx0Gj0k-0PDay-hxlp6fnFKDO1tVmrisiaffUcfh4dByEuifrbotnG5CUX0Q1m0Yfacid22xDVi_YB2EXqGJqdNZKWmI3xxzpOUSqNGoynxClnYjjjOiFjk03ItytIadrMSuqqpdrue3O0kQUvo2Hl99lzsowciFlvkwOrVhOvN4NIeFYE7BFR_MWDekTwwSB3OVCw_15qtbJ677A_00pyMndG7ebCkxahB-crMN3peFXh2Bz4LndG454O10='  # Ganti dengan string session yang Anda dapatkan

# Your API ID and Hash from my.telegram.org
api_id = '29534642'
api_hash = '0163712ff5842fa356424ad75a53442b'
phone = '+6283116571651'

# Chat ID grup atau channel untuk menyimpan media
target_chat_id = '@filebotkep'

client = TelegramClient(StringSession(string_session), api_id, api_hash, connection_retries=5)  # Menambahkan retry

# Setup logging
logging.basicConfig(level=logging.INFO)

# Penanda untuk menghentikan proses
stop_process = False
downloaded_media_ids = set()  # Set untuk melacak ID media yang sudah diunduh

@client.on(events.NewMessage(pattern=r'/download'))
async def download_media(event):
    global stop_process, downloaded_media_ids
    user_input = event.raw_text.split(maxsplit=1)[1]
    stop_process = False  # Reset penanda
    downloaded_media_ids.clear()  # Reset set media yang sudah diunduh
    try:
        if user_input.startswith('@'):
            link = user_input
        elif re.match(r'https://t\.me/c/\d+/\d+', user_input):
            link = user_input
        else:
            link = int(user_input.strip())

        entity = await client.get_entity(link)

        # Bergabung dengan channel atau grup jika belum bergabung
        if isinstance(entity, (PeerChannel, PeerChat)):
            await client(JoinChannelRequest(entity))
            await event.respond(f"Berhasil bergabung dengan {link}.")

        total_files = 0

        async for message in client.iter_messages(entity):
            if stop_process:
                await event.respond("Proses pengunduhan dihentikan.")
                return
            if isinstance(message.media, MessageMediaPhoto) or isinstance(message.media, MessageMediaDocument):
                if message.id not in downloaded_media_ids:
                    total_files += 1

        await event.respond(f"Ditemukan {total_files} media. Memulai proses pengunduhan...")

        progress = 0
        async for message in client.iter_messages(entity):
            if stop_process:
                await event.respond("Proses pengunduhan dihentikan.")
                return
            if isinstance(message.media, MessageMediaPhoto) or isinstance(message.media, MessageMediaDocument):
                if message.id not in downloaded_media_ids:
                    await handle_and_send_media(message, entity, total_files, progress)
                    progress += 1
                    await update_progress(event, total_files, progress)

        await event.respond(f"Semua media dari {link} berhasil diunduh dan diteruskan ke {target_chat_id}.")
    except Exception as e:
        await event.respond(f"Gagal mengunduh media. Error: {e}\nUsage: /download <@username or channel_id or link>")

@client.on(events.NewMessage(pattern=r'/stop'))
async def stop_handler(event):
    global stop_process
    stop_process = True
    await event.respond("Proses sedang dihentikan...")

@client.on(events.NewMessage(pattern=r'/internet'))
async def internet_speed(event):
    try:
        st = speedtest.Speedtest()
        st.get_servers()
        best_server = st.get_best_server()
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        ping = best_server['latency']

        await event.respond(f"Kecepatan Internet Server:\nServer Terbaik: {best_server['host']} di {best_server['country']}\nDownload: {download_speed:.2f} Mbps\nUpload: {upload_speed:.2f} Mbps\nPing: {ping} ms")
    except speedtest.ConfigRetrievalError:
        await event.respond("Gagal mendapatkan konfigurasi server. Pastikan Anda terhubung ke internet.")
    except speedtest.NoMatchedServers:
        await event.respond("Gagal menemukan server yang cocok untuk tes kecepatan.")
    except Exception as e:
        await event.respond(f"Gagal mendapatkan kecepatan internet. Error: {e}")

@client.on(events.NewMessage(pattern=r'/status'))
async def status_handler(event):
    try:
        await event.respond("Userbot aktif dan berjalan dengan baik!")
    except Exception as e:
        await event.respond(f"Gagal memeriksa status. Error: {e}")

@client.on(events.NewMessage())
async def forward_media(event):
    if event.is_private and (isinstance(event.media, MessageMediaPhoto) or isinstance(event.media, MessageMediaDocument)):
        await handle_and_send_media(event.message, event.chat, 1, 0)

async def handle_and_send_media(message, entity, total_files, progress):
    global stop_process, downloaded_media_ids
    try:
        if stop_process:
            return
        file_type = 'photo' if isinstance(message.media, MessageMediaPhoto) else 'video'
        file_id = message.media.photo.id if file_type == 'photo' else message.media.document.id

        # Unduh media dengan menangani perpindahan Data Center
        file_path = await download_media_with_dc_handling(message)
        
        # Tambahkan ID media ke set downloaded_media_ids
        downloaded_media_ids.add(message.id)

        # Dapatkan informasi pengirim
        try:
            sender = await message.get_sender()
            username = f"@{sender.username}" if sender.username else 'Tidak ada'
            user_id = sender.id
        except Exception:
            username = 'Tidak ada'
            user_id = 'Tidak diketahui'
        
        # Format waktu dan tanggal
        tz = pytz.timezone('Asia/Jakarta')
        time_sent = message.date.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # Kirim media ke target chat dengan format baru
        caption = f"Oleh: {username} (ID: {user_id})\nDikirim pada: {time_sent} (GMT+7)"
        await client.send_file(target_chat_id, file_path, caption=caption)
        logging.info(f"{file_type.capitalize()} downloaded and sent to {target_chat_id} with caption.")

        # Tambahkan jeda kecil untuk mencegah beban berlebih
        await asyncio.sleep(0.2)
    except Exception as e:
        logging.error(f"Error processing media: {e}")

async def download_media_with_dc_handling(message):
    try:
        return await message.download_media()
    except errors.FileMigrateError as e:
        # Berpindah Data Center jika diperlukan
        await client.disconnect()
        client.session.set_dc(e.new_dc, client.session.server_address, client.session.port)
        await client.connect()
        # Mengunduh ulang media setelah berpindah Data Center
        return await message.download_media()

async def update_progress(event, total_files, progress):
    percentage = (progress / total_files) * 100
    await event.respond(f'Progres pengunduhan: {percentage:.2f}% ({progress}/{total_files}) media telah diunduh.')

def main():
    client.start(phone)
    print("Userbot is running...")
    client.run_until_disconnected()

if __name__ == '__main__':
    main()
