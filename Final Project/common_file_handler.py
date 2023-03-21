import os
import threading as th

class file_input_output():
    def __init__(self, file_path):
        self.file_descriptor = os.open(file_path, os.O_RDWR | os.O_CREAT)

    # writes in file at particular location
    def write(self, byte_stream):
        os.write(self.file_descriptor, byte_stream)   
   
    # writes file with all values to 0(null) given the size of file
    def init_with_null(self, file_size):
        max_write_space = (2 ** 14)  #16KB
        # move the file descripter to the 0th index position from start of file
        self.move_to_write_position(0)
        while(file_size > 0):
            if file_size >= max_write_space:
                file_size = file_size - max_write_space
                null_data = b'\x00' * max_write_space
            else:
                null_data = b'\x00' * file_size
                file_size = 0
            self.write(null_data)

    def move_to_write_position(self, index_position):
        os.lseek(self.file_descriptor, index_position, os.SEEK_SET)
            
class torrent_common_file_handler():
    
    def __init__(self, download_file_path, torrent):
        self.download_file_path = download_file_path
        self.torrent = torrent
        
        # file size in bytes
        self.file_size = torrent.torrent_metadata.fileSize
        # piece size in bytes of torrent file data
        self.piece_size = torrent.torrent_metadata.pieceLength

        self.download_file = file_input_output(self.download_file_path)

        # shared file lock
        self.shared_file_lock = th.Lock()
        
    def initialize_for_download(self):
        self.download_file.init_with_null(self.file_size)
    
    # calculates the position index in file 
    def get_file_position(self, piece_index, block_offset):
        return piece_index * self.piece_size + block_offset

    def initalize_file_descriptor(self, piece_index, block_offset):
        
        # calulcate the position in file 
        file_descriptor_position = self.get_file_position(piece_index, block_offset)
        # move the file descripter to the desired location 
        self.download_file.move_to_write_position(file_descriptor_position)

    # helps in writing in file
    def write_block(self, piece_message):  
        piece_index     = piece_message.piece_index
        block_offset    = piece_message.block_offset
        data_block      = piece_message.block
        
        self.shared_file_lock.acquire()
        # initialize the file descriptor at given piece index and block offset
        self.initalize_file_descriptor(piece_index, block_offset)

        # write the block of data into the file
        self.download_file.write(data_block)
        self.shared_file_lock.release()
