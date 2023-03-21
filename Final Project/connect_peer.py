from socket import *
from copy import deepcopy
import threading as th
import struct
import time
import random
import hashlib
from messages import *


# constant handshake message length
LEN_OF_HANDSHAKE = 68
# constants indicating the message sizes in PWM
LEN_OF_MSG = 4
MSG_ID_SIZE = 1

class swarm():

    def __init__(self, peers_data, torrent):
        # initialize the peers class with peer data recieved
        self.torrent    = deepcopy(torrent)
        self.interval   = peers_data['interval']
        self.seeders    = peers_data['seeders']
        self.leechers   = peers_data['leechers']
     
        self.peers_list = []
        for peer_IP, peer_port in peers_data['peers']:
            self.peers_list.append(peer(peer_IP, peer_port, torrent))
        
        # file handler for downloading file data
        self.file_handler = None

        # bitfields from all peers
        self.bitfield_pieces_count = dict()

        # bitfield for pieces downloaded from peers
        self.bitfield_pieces_downloaded = set([])

        # selecting the top N peers / pieces
        self.top_n = self.torrent.client_request['max peers']
        # swarm lock for required for updating the global state
        self.swarm_lock = th.Lock()

    
    # function helps in making the share copy of handler available to peers
    def add_common_file_handler(self, file_handler):
        self.file_handler = file_handler
        for peer in self.peers_list:
            peer.file_handler = self.file_handler

    # updates the global state of count of number of peers having a piece
    def update_bitfield_count(self, bitfield_pieces):
        for piece in bitfield_pieces:
            if piece in self.bitfield_pieces_count.keys():
                self.bitfield_pieces_count[piece] += 1
            else:
                self.bitfield_pieces_count[piece] = 1


    # function performs the initial connection with peer by doing handshakes 
    def connect_to_peer(self, peer_index):
        self.peers_list[peer_index].start_Handshake()

        # further handle bit_field response from the peer
        peer_bitfield_pieces = self.peers_list[peer_index].initialize_bitfield()

        self.swarm_lock.acquire()   #locking the lock
        # update the bitfield count value in swarm
        self.update_bitfield_count(peer_bitfield_pieces) 
        self.swarm_lock.release()

    # function helps in downloading torrrent file from peers
    def file_Download(self):
        if not self.file_handler:
            return False
        for peer_index in range(len(self.peers_list)):
            peer_conn_thread = th.Thread(target = self.connect_to_peer, args=(peer_index, ))
            peer_conn_thread.start()
        # further start download thread to download pieces of file from peers
        download_thread = th.Thread(target = self.download_strategy)
        download_thread.start()

    # downloads the file from peers in swarm using some stratergies
    def download_strategy(self):
        self.download_start_time = time.time()
        while not (len(self.bitfield_pieces_downloaded) == self.torrent.pieces_count):   # until download is complete
            # select the pieces and peers for downloading
            pieces = self.piece_selection_startergy()
            peer_indexes = self.peer_selection_startergy()

            # download the rarest pieces from the top four randomly selected peers
            downloading_thread_list = []
            for i in range(min(len(pieces), len(peer_indexes))):
                piece = pieces[i]
                peer_index = peer_indexes[i]
                downloading_thread = th.Thread(target=self.piece_download, args=(piece, peer_index, ))
                downloading_thread_list.append(downloading_thread)
                downloading_thread.start()
            print("<-- Number of pieces download -->",len(self.bitfield_pieces_downloaded),"\n\n")  
            # wait until finish the downloading of the pieces
            for downloading_thread in downloading_thread_list:
                downloading_thread.join()
        self.download_end_time = time.time()
        

    # rarest first piece selection stratergy
    def piece_selection_startergy(self):
        # check if bitfields are recieved else wait for some time
        while(len(self.bitfield_pieces_count) == 0):
            time.sleep(5)
        # get the rarest pieces
        rarest_piece_count = min(self.bitfield_pieces_count.values())
        # there can be multiple rareset pieces
        rarest_pieces = [piece for piece in self.bitfield_pieces_count if 
                         self.bitfield_pieces_count[piece] == rarest_piece_count] 
        # shuffle among the random pieces 
        random.shuffle(rarest_pieces)
        print("<<-----Top ",self.top_n," Rarest Pieces----->>")
        return rarest_pieces[:self.top_n]

    # randomly selecting peers and returning their index
    def peer_selection_startergy(self):
        peer_indexes = []
        # select all the peers that have pieces to offer
        for index in range(len(self.peers_list)):
            if len(self.peers_list[index].bitfield_pieces) != 0:
                peer_indexes.append(index)
        random.shuffle(peer_indexes)
        return peer_indexes[:self.top_n]

    # function downloads piece given the peer index and updating bitfield_pieces_downloaded
    def piece_download(self, piece, peer_index):
        is_piece_downloaded = self.peers_list[peer_index].piece_downloading_states(piece)
        if is_piece_downloaded:
            self.swarm_lock.acquire() 
            # update the bifields pieces downloaded
            self.bitfield_pieces_downloaded.add(piece)
            # delete the pieces from the count of pieces
            del self.bitfield_pieces_count[piece]
            self.swarm_lock.release()

# peer class instance maintains the information about the peer participating in the file sharing.
class peer():
    def __init__(self, peer_IP, peer_port, torrent, init_peer_socket = None):
        self.IP         = peer_IP
        self.port       = peer_port
        self.torrent    = deepcopy(torrent)
        
        # initialize the state_of_peer
        self.state = state_of_peer()

        # string used for idenfiying the peer
        self.unique_id  = '(' + self.IP + ' : ' + str(self.port) + ')'
        
        # unique peer ID recieved from peer
        self.peer_id = None

        # maximum download block message length 
        self.max_block_length = torrent.block_length   #16Kb
        
        # handshake flag with peer
        self.handshake_flag = False
        
        self.peerSocket = peer_socket(self.IP, self.port, init_peer_socket)
            
        # for reading/writing
        self.file_handler = None

        # bitfield representing which data file pieces peer has
        self.bitfield_pieces = set([])

        # response message handler for recieved message
        self.response_handler = { KEEP_ALIVE_ID    : self.recieved_keep_alive,
                                  CHOKE_ID         : self.recieved_choke,
                                  UNCHOKE_ID       : self.recieved_unchoke,
                                  HAVE_ID          : self.recieved_have, 
                                  BITFIELD_ID      : self.recieved_bitfield,
                                  PIECE_ID         : self.recieved_piece,
                                   }

        # keep alive timeout : 10 second
        self.keep_alive_timeout = 10
        # keep alive timer
        self.keep_alive_timer = None

    def create_handshake_msg(self):
        info_hash = self.torrent.torrent_metadata.info_hash
        peer_id   = self.torrent.peer_id
        # create a handshake object instance
        return handshake(info_hash, peer_id)
 
    def send_handshake(self):
        handshake_request = self.create_handshake_msg()
        self.peerSocket.send_data(handshake_request.message())
        handshake_req_msg = 'Handshake started -----> ' + self.unique_id
        print(handshake_req_msg)

        return handshake_request


    # function returns handshake recieved on success else returns None
    def get_handshake(self):
        # recieve message for the peer
        raw_handshake_resp = self.peerSocket.get_data(LEN_OF_HANDSHAKE)  #68
        if raw_handshake_resp is None:
            handshake_res = 'Handshake not answered from ' + self.unique_id
            print(handshake_res)
            return None
    
        handshake_res = 'Handshake answered   <----- ' + self.unique_id
        print(handshake_res)

        return raw_handshake_resp

    def send_connection(self):
        connection_status = None
        if self.peerSocket.req_connection():
            connection_status = True
        else:
            connection_status = False
        return connection_status

    
    # functions helpes in recieving peer wire protocol messages and
    #  returns P2P_msg class object. 
    def recieve_message(self):
        # recieve the message length 
        RawMessageLength = self.peerSocket.get_data(LEN_OF_MSG) 
          #only recieve length of message which is 4 bytes long and afterwards 1 byte of Message ID
        if RawMessageLength is None or len(RawMessageLength) < LEN_OF_MSG:
            return None

        # unpack the message length 
        MessageLength = struct.unpack_from("!I", RawMessageLength)[0]
        # keep alive messages have no message ID and payload
        if MessageLength == 0:
            return P2P_msg(MessageLength, None, None)

        # attempt to recieve the message ID from message
        RawMessageID =  self.peerSocket.get_data(MSG_ID_SIZE)
        if RawMessageID is None:
            return None
        
        # unpack the message ID which is 1 bytes long
        MessageID  = struct.unpack_from("!B", RawMessageID)[0]
        # messages having no payload 
        if MessageLength == 1:
            return P2P_msg(MessageLength, MessageID, None)
       
        # get all the payload
        payloadLength = MessageLength - 1
        
        msgPayload =self.peerSocket.get_data(payloadLength)
        if msgPayload is None:
            return None
        
        # keep alive timer updated 
        self.keep_alive_timer = time.time()
        
        return P2P_msg(MessageLength, MessageID, msgPayload)

    """
        function helps in sending peer messgae given peer wire message 
        class object as an argument to the function
    """
    def send_message(self, peer_request):
        if self.handshake_flag:
            # used for EXCECUTION LOGGING
            peer_request_msg = 'sending message  -----> ' + peer_request.__str__() 
            print(peer_request_msg)
            # send the message 
            self.peerSocket.send_data(peer_request.message())
 

    # functions returns success/failure result of handshake 
    def start_Handshake(self):
        # only do handshake if not earlier and established TCP connection
        if not self.handshake_flag and self.send_connection():
            handshake_request = self.send_handshake()
            raw_handshake_resp = self.get_handshake()
            if raw_handshake_resp is None:
                return False
            # validate the hanshake message recieved obtained
            handshake_resp = self.isValid_handshake(raw_handshake_resp)
            if handshake_resp is None:
                return False
            # get the client peer id for the handshake response
            self.peer_id = handshake_resp.client_peer_id
            self.handshake_flag = True
            return True
        # already attempted handshake with the peer
        return False

    def isValid_handshake(self, raw_handshake_resp):
        # attempt validation of raw handshake response with handshake request
        try:
            handshake_request = self.create_handshake_msg()
            handshake_resp = handshake_request.validate_handshake(raw_handshake_resp)
            print("SUCCESSFULLY VALIDATED!!!!")
            return handshake_resp
        except Exception as error_msg:
            print(error_msg)
            return None


    # function helps in initializing the bitfield values 
    def initialize_bitfield(self):
        if not self.peerSocket.peer_Conn:
            return self.bitfield_pieces   # empty set
        # recieve only if handshake is done successfully "
        if not self.handshake_flag:
            return self.bitfield_pieces   # empty set
        # handle all the messages that are recieved by the peer
        messages_begin_recieved = True
        while(messages_begin_recieved):
            # handle responses recieved
            response_message = self.handle_response()
            if response_message is None: 
                messages_begin_recieved = False
        return self.bitfield_pieces

  
    # function handles peer message and decodes the message and also react to it
    # else returns None
    def handle_response(self):
        
        peer_response_message = self.recieve_message()
        if peer_response_message is None:
            return None
        # DECODE the message into appropriate message type 
        decoded_message = decode(peer_response_message)
        if decoded_message is None:
            return None

        recieved_message = 'Recieved Message <----- ' + decoded_message.__str__() 
        print(recieved_message)

        # further REACT to the message accordingly
        self.handle_message(decoded_message)
        return decoded_message
    
    # this function responds to the type of message received
    def handle_message(self, decoded_message):
        # select the respective message handler 
        message_handler = self.response_handler[decoded_message.message_id]
        # handle the deocode response message
        return message_handler(decoded_message)


    """
        disconnects the peer socket connection
    """
    def close_peer_connection(self):
        self.state.set_null()
        self.peerSocket.disconnect()


        #_______________________________________________________________________________________
        #| ----------------------RECIVED MESSAGES HANDLER FUNCTIONS --------------------------- |
        #|______________________________________________________________________________________|
    
    # if peer is still active
    def recieved_keep_alive(self,keep_alive_message):
         # updating the timer
         self.keep_alive_timer = time.time()

    # Client is choked and hence peer won't respond to client request
    def recieved_choke(self,choke_message):
        # peer is choking the client
        self.state.set_peer_choking()
        # client will also be not interested if peer is choking
        self.state.set_client_not_interested()


    # Client is unchoked and hence peer will respond to client request
    def recieved_unchoke(self,unchoke_message):
        # the peer is unchoking the client
        self.state.set_peer_unchoking()
        # the peer in also interested in the client
        self.state.set_client_interested()


    # peer sends the bitfiled values to client after handshaking
    def recieved_bitfield(self, bitfield_message):
        # extract the piece information from the bitfield message
        self.bitfield_pieces = bitfield_message.extract_pieces()

    # peer sends information of piece that it has
    def recieved_have(self, have_message):
        # update the piece information in the peer bitfiled 
        self.bitfield_pieces.add(have_message.piece_index) 
    
    # peer sends the piece data,the received piece is written in file
    def recieved_piece(self, piece_message):
        # write the block of piece into the file
        self.file_handler.write_block(piece_message)

    # client is interested in the peer
    def send_interested(self):
        self.send_message(interested())
        self.state.set_client_interested()

    # sequence of states to be followed during download of a piece
    def piece_downloading_states(self, piece_index):
        if not self.have_piece(piece_index):
            return False
        self.keep_alive_timer = time.time()
        # download status of piece
        download_status = False
        keep_looking = True
        while keep_looking:
            # checking for timeouts in states 
            if(self.check_keep_alive_timeout()):
                self.state.set_null()
            # client state 0    : (client = not interested, peer = choking)
            if(self.state == STATE0):
                self.send_interested()
            # client state 1    : (client = interested, peer = choking)
            elif(self.state == STATE1):
                response_message = self.handle_response()
            # client state 2    : (client = interested, peer = not choking)
            elif(self.state == STATE2):
                download_status = self.piece_download(piece_index)
                keep_looking = False
            # client state 3    : (client = None, peer = None)
            elif(self.state == STATE3):
                keep_looking = False
        return download_status

    # if keep alive msg not received for some time
    def check_keep_alive_timeout(self):
        if(time.time() - self.keep_alive_timer >= self.keep_alive_timeout):
            keep_alive_msg = self.unique_id + ' peer keep alive timeout ! ' + 'FAILURE' 
            keep_alive_msg+= ' disconnecting the peer connection!'
            self.close_peer_connection()
            print(keep_alive_msg)
            return True
        else:
            return False


    # function helps in downloading the given piece from the peer
    def piece_download(self, piece_index):
        if not self.have_piece(piece_index) or not self.is_download_possible():
            return False

        # received piece data
        recieved_piece = b''  
        block_offset = 0
        block_length = 0
        # piece length for torrent 
        piece_length = self.torrent.get_piece_length(piece_index)
        
        # loop until download all the blocks in the piece
        while self.is_download_possible() and block_offset < piece_length:
            # length of block that can be requested
            if piece_length - block_offset >= self.max_block_length:
                block_length = self.max_block_length
            else:
                block_length = piece_length - block_offset
            
            block_data = self.block_download(piece_index, block_offset, block_length)
            if block_data:
                # increament offset according to size of data block recieved
                recieved_piece += block_data
                block_offset   += block_length
        
        # check for connection timeout
        if self.check_keep_alive_timeout():
            return False
        
        # validate the piece and update the peer downloaded bitfield
        if(not self.piece_validating(recieved_piece, piece_index)):
            return False
    
        download_msg  = self.unique_id + ' downloaded piece : '
        download_msg += str(piece_index) + ' ' + 'SUCCESS'  
        print(download_msg)
        
        # successfully downloaded and validated piece 
        return True

    
    #  downloading given block of the piece from peer
    def block_download(self, piece_index, block_offset, block_length):
        # create a request message 
        request_message = request(piece_index, block_offset, block_length)
        self.send_message(request_message) 
        response_message = self.handle_response()
        
        # if the message recieved was not a piece message
        if not response_message or response_message.message_id != PIECE_ID:
            return None
        # validate the response
        if not self.validate_request_piece_messages(request_message, response_message):
            return None

        # successfully downloaded and validated block of piece
        return response_message.block

    def is_download_possible(self):
        # socket connection still active
        if not self.peerSocket.peer_Conn:
            return False
        # if peer has not done handshake 
        if not self.handshake_flag:
            return False
        # check if peer is interested and peer is not choking
        if self.state != STATE2:
            return False
        if self.check_keep_alive_timeout():
            return False
        return True

    # checks if peer has piece
    def have_piece(self, piece_index):
        if piece_index in self.bitfield_pieces:
            return True
        else:
            return False

    def add_file_handler(self, file_handler):
        self.file_handler = file_handler
    

    # validates the block recieved
    def validate_request_piece_messages(self, request, piece):
        if request.piece_index != piece.piece_index:
            return False
        if request.block_offset != piece.block_offset:
            return False
        if request.block_length != len(piece.block):
            return False
        return True

    # validates the piece recieved
    def piece_validating(self, piece, piece_index):
        # compare the length of the piece recieved
        piece_length = self.torrent.get_piece_length(piece_index)
        if (len(piece) != piece_length):
            download_msg  = self.unique_id + 'unable to downloaded piece ' 
            download_msg += str(piece_index) + ' due to validation failure : ' 
            download_msg += 'incorrect lenght ' + str(len(piece)) + ' piece recieved '
            download_msg += 'FAILURE'
            print(download_msg)
            return False

        piece_hash = hashlib.sha1(piece).digest()
        index = piece_index * 20
        torrent_piece_hash = self.torrent.torrent_metadata.pieces[index : index + 20]
        
        # compare the pieces hash with torrent file piece hash
        if piece_hash != torrent_piece_hash:
            download_msg  = self.unique_id + 'unable to downloaded piece ' 
            download_msg += str(piece_index) + ' due to validation failure : ' 
            download_msg += 'info hash of piece not matched ' + 'FAILURE'
            print(download_msg)
            return False
        return True 
        
# maintains the state of peer participating in downloading
class state_of_peer():
    def __init__(self):
        # Initialize the states of the peer 
        self.am_choking = True              # client choking peer
        self.am_interested = False             # client interested in peer
        self.peer_choking = True              # peer choking client
        self.peer_interested = False             # peer interested in clinet

    def set_client_choking(self):
        self.am_choking = True
    def set_client_unchoking(self):
        self.am_choking = False
 
    def set_client_interested(self):
        self.am_interested = True
    def set_client_not_interested(self):
        self.am_interested = False

    def set_peer_choking(self):
        self.peer_choking = True
    def set_peer_unchoking(self):
        self.peer_choking = False

    def set_peer_interested(self):
        self.peer_interested = True
    def set_peer_not_interested(self):
        self.peer_interested = False
    
    def set_null(self):
        self.am_choking         = None
        self.am_interested      = None
        self.peer_choking       = None
        self.peer_interested    = None

    # overaloading == operation for comparsion with states
    def __eq__(self, other): 
        if self.am_choking != other.am_choking :
            return False
        if self.am_interested != other.am_interested:
            return False
        if self.peer_choking != other.peer_choking: 
            return False
        if self.peer_interested != other.peer_interested:
            return False
        return True
    
    # overaloading != operation for comparsion with states
    def  __ne__(self, other):
        return not self.__eq__(other)

# class for peer socket 
class peer_socket():

    def __init__(self, peer_IP, peer_port, psocket = None):
        if psocket is None:
            self.peerSocket = socket(AF_INET, SOCK_STREAM)
            self.peer_Conn = False
        else:
            self.peer_Conn = True
            self.peerSocket = psocket
        
        self.timeout = 3
        self.peerSocket.settimeout(self.timeout)
        
        # IP and port of the peer
        self.IP = peer_IP
        self.port = peer_port
        self.unique_id = self.IP + ' ' + str(self.port)

    def req_connection(self):
        try:
            self.peerSocket.connect((self.IP, self.port))
            self.peer_Conn = True
        except Exception as err:
            print(err,self.IP)
            self.peer_Conn = False
        return self.peer_Conn

    def send_data(self, raw_data):
        if not self.peer_Conn:
            return False
        try:
            self.peerSocket.send(raw_data)
        except:
            # the TCP connection is broken
            return False
        return True

   # receive all the data of particular length
    def get_data(self, data_size):
        if not self.peer_Conn:
            return 
        peer_raw_data = b''
        recieved_data_length = 0
        request_size = data_size
        
        # loop until you recieve all the data from the peer
        while(recieved_data_length < data_size):
            # attempt recieving requested data size in chunks
            try:
                specific_piece = self.peerSocket.recv(request_size)
            except:
                specific_piece = b''
            if len(specific_piece) == 0:
                return None
            peer_raw_data += specific_piece
            request_size -=  len(specific_piece)
            recieved_data_length += len(specific_piece)

        return peer_raw_data

    def disconnect(self):
        self.peerSocket.close() 
        self.peer_connection = False 

# initialize the handshake with the payload 
class handshake():
    
    def __init__(self, info_hash, client_peer_id):  
        self.protocol_name = "BitTorrent protocol"
        self.info_hash = info_hash 
        self.client_peer_id = client_peer_id

    # creates the handshake payload for peer wire protocol handshake
    def message(self):
        # first bytes the length of protocol name default - 19
        handshake_msg = struct.pack("!B", len(self.protocol_name))
        # protocol name 19 bytes
        handshake_msg += struct.pack("!19s", self.protocol_name.encode())
        # next 8 bytes reserved 
        handshake_msg  += struct.pack("!Q", 0x0)
        # next 20 bytes info hash
        handshake_msg += struct.pack("!20s", self.info_hash)
        # next 20 bytes peer id
        handshake_msg  += struct.pack("!20s", self.client_peer_id)
        
        return handshake_msg


    # validate the response handshake else raise the error
    def validate_handshake(self, response_handshake):

        # compare the handshake length
        handshake_response_len = len(response_handshake)
        if(handshake_response_len != LEN_OF_HANDSHAKE):
            error_msg = 'Invalid handshake length ( ' + str(handshake_response_len) + 'B )'
            print(error_msg)
        
        # get the info hash of torrent 
        peer_info_hash = response_handshake[28:48]
        # get the peer id 
        peer_id = response_handshake[48:68]

        # check if the info hash is equal 
        if(peer_info_hash != self.info_hash):
            error_msg = 'Info hash with peer of torrent do not match !'
            print(error_msg)

        # check if peer has got a unique id associated with it
        if(peer_id == self.client_peer_id):
            error_msg = 'Peer ID and client ID both match drop connection !'
            print(error_msg)

        # succesfully validating 
        return handshake(peer_info_hash, peer_id)

# FSM 
# initial state     : client = not interested, peer = choking
STATE0 = state_of_peer()

# client state 1    : client = interested, peer = choking
STATE1 = state_of_peer()
STATE1.am_interested   = True
    
# client state 2    : client = interested, peer = not choking
STATE2 = state_of_peer()
STATE2.am_interested   = True
STATE2.peer_choking    = False

# client state 3    : client : None, peer = None
STATE3 = state_of_peer()
STATE3.set_null()
