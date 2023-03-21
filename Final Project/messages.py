import struct

# constants indicating ID's for each message
KEEP_ALIVE_ID = None
CHOKE_ID = 0
UNCHOKE_ID = 1 
INTERESTED_ID = 2
UNINTERESTED_ID = 3
HAVE_ID = 4
BITFIELD_ID = 5
REQUEST_ID = 6
PIECE_ID = 7


class P2P_msg():
    
    def __init__(self, message_length, message_id, payload):
        self.message_length = message_length
        self.message_id     = message_id 
        self.payload        = payload

    # returns raw message
    def message(self):
        message  = struct.pack("!I", self.message_length)
        if self.message_id != None:
            message += struct.pack("!B", self.message_id)
        if self.payload != None:
            message += self.payload
        return message
    
class keep_alive(P2P_msg):
    def __init__(self):   
        message_length  = 0                                 
        message_id = KEEP_ALIVE_ID                        
        payload = None                           
        super().__init__(message_length, message_id, payload)
    
    def __str__(self):
        message  = 'KEEP ALIVE -> '
        message += '[message length : ' + str(self.message_length) + '], '
        message += '[message id : None], '
        message += '[message paylaod : None]'
        return message

class choke(P2P_msg):
    def __init__(self):   
        message_length = 1                                 
        message_id = CHOKE_ID                             
        payload = None                               
        super().__init__(message_length, message_id, payload)

    def __str__(self):
        message  = 'CHOKE_ID : '
        message += '[message length : ' + str(self.message_length)  + '], '
        message += '[message id : '     + str(self.message_id)      + '], '
        message += '[message paylaod : None]'
        return message

class unchoke(P2P_msg):
    def __init__(self):   
        message_length = 1                                 
        message_id = UNCHOKE_ID                            
        payload = None                              
        super().__init__(message_length, message_id, payload)

    def __str__(self):
        message  = 'UNCHOKE_ID : '
        message += '[message length : ' + str(self.message_length)  + '], '
        message += '[message id : '     + str(self.message_id)      + '], '
        message += '[message paylaod : None]'
        return message

class interested(P2P_msg):
    def __init__(self):   
        message_length = 1                                  
        message_id = INTERESTED_ID                         
        payload = None                             
        super().__init__(message_length, message_id, payload)

    def __str__(self):
        message  = 'INTERESTED_ID : '
        message += '[message length : ' + str(self.message_length)  + '], '
        message += '[message id : '     + str(self.message_id)      + '], '
        message += '[message paylaod : None]'
        return message

class uninterested(P2P_msg):
    def __init__(self):   
        message_length = 1                                
        message_id = UNINTERESTED_ID                      
        payload = None                              
        super().__init__(message_length, message_id, payload)

    def __str__(self):
        message  = 'UNINTERESTED_ID : '
        message += '[message length : ' + str(self.message_length)  + '], '
        message += '[message id : '     + str(self.message_id)      + '], '
        message += '[message paylaod : None]'
        return message

class have(P2P_msg):
    def __init__(self, piece_index):   
        message_length = 5                                  
        message_id = HAVE_ID                               
        payload = struct.pack("!I", piece_index)     # 4 bytes payload
        super().__init__(message_length, message_id, payload)
        self.piece_index = piece_index

    def __str__(self):
        message  = 'HAVE_ID : '
        message += '[message length : ' + str(self.message_length)  + '], '
        message += '[message id : '     + str(self.message_id)      + '], '
        message += '[message paylaod : [piece index : ' + str(self.piece_index) + '])'
        return message

class bitfield(P2P_msg):
    def __init__(self, pieces_info):
        message_length = 1 + len(pieces_info)              
        message_id = BITFIELD_ID                          
        payload = pieces_info                       # variable length payload
        super().__init__(message_length, message_id, payload)
        # actual payload data to be send
        self.pieces_info = pieces_info

    # extract downloaded pieces from bitfield send by peer 
    def extract_pieces(self):
        bitfield_pieces = set([])
        # looping through eqch byte
        for i, byte_value in enumerate(self.payload):
            for j in range(8):
                # check if jth bit is set
                if((byte_value >> j) & 1):
                    piece_number = i * 8 + 7 - j
                    bitfield_pieces.add(piece_number)
        # return the set with the piece numbers that peer has
        return bitfield_pieces

    def __str__(self):
        message  = 'BITFIELD_ID : '
        message += '(message paylaod : [bitfield length : ' + str(len(self.pieces_info)) + '])'
        return message

class request(P2P_msg):
    # request message for any given block from any piece  
    def __init__(self, piece_index, block_offset, block_length):
        message_length  = 13                               
        message_id = REQUEST_ID                           
        payload = struct.pack("!I", piece_index)    # 12 bytes payload
        payload += struct.pack("!I", block_offset) 
        payload += struct.pack("!I", block_length) 
        super().__init__(message_length, message_id, payload)
        # actual payload data to be associated with object
        self.piece_index    = piece_index
        self.block_offset   = block_offset
        self.block_length   = block_length
        

    def __str__(self):
        message  = 'REQUEST_ID : '
        message += '(message paylaod : [ '
        message += 'piece index : '     + str(self.piece_index)     + ', '
        message += 'block offest : '    + str(self.block_offset)    + ', '
        message += 'block length : '    + str(self.block_length)    + ' ])'
        return message

class piece(P2P_msg):
    # the piece message for any block data from file
    def __init__(self, piece_index, block_offset, block):
        message_length = 9 + len(block)                    
        message_id = PIECE_ID                            
        payload  = struct.pack("!I", piece_index)    # variable length payload
        payload += struct.pack("!I", block_offset)
        payload += block
        super().__init__(message_length, message_id, payload)
        # actual payload data to be associated with object
        self.piece_index    = piece_index
        self.block_offset   = block_offset
        self.block          = block 

    def __str__(self):
        message  = 'PIECE_ID : '
        message += '(message paylaod : [ '
        message += 'piece index : '     + str(self.piece_index)     + ', '
        message += 'block offest : '    + str(self.block_offset)    + ', '
        message += 'block length : '    + str(len(self.block))      + ' ])'
        return message

def decode(peer_message):

    # decodes the given peer_message
    if peer_message.message_id == KEEP_ALIVE_ID :
        decoded_message = keep_alive()

    elif peer_message.message_id == CHOKE_ID :    
        decoded_message = choke()

    elif peer_message.message_id == UNCHOKE_ID :        
        decoded_message = unchoke()

    elif peer_message.message_id == INTERESTED_ID :     
        decoded_message = interested()

    elif peer_message.message_id == UNINTERESTED_ID :
        decoded_message = uninterested()

    elif peer_message.message_id == HAVE_ID :
        piece_index = struct.unpack_from("!I", peer_message.payload)[0]
        decoded_message = have(piece_index)

    elif peer_message.message_id == BITFIELD_ID :
        decoded_message = bitfield(peer_message.payload)

    elif peer_message.message_id == REQUEST_ID :        
        piece_index  = struct.unpack_from("!I", peer_message.payload, 0)[0]
        block_offset = struct.unpack_from("!I", peer_message.payload, 4)[0]
        block_length = struct.unpack_from("!I", peer_message.payload, 8)[0]
        decoded_message = request(piece_index, block_offset, block_length)

    elif peer_message.message_id == PIECE_ID :          
        piece_index  = struct.unpack_from("!I", peer_message.payload, 0)[0]
        begin_offset = struct.unpack_from("!I", peer_message.payload, 4)[0]
        block = peer_message.payload[8:]
        decoded_message = piece(piece_index, begin_offset, block)

    return decoded_message
