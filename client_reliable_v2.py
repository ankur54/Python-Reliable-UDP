import socket
import threading
import time

# Global Variables:

sender_packet = {}              # mapping from user to the last packet number that it sent 
reciever_packet = {}            # mapping from user to (sequence number, mesege) that the user sent
last_print = {}                 # last message number that was printed for each user
message_queue = []              # queues the message along with seq number for it to be sent
buff = []                       # stores the messages that had arrived at reciever for processing
owner = ''                      # stores the owner name of the login system
ack_list = {}                   # stores the list of ACK numbers that has correctly recieved the message for each user  
delay = 20.0                    # specifies the time to wait for ACK for the message sent 
msg_key = '1001'                # the static key for error detection


# Logic for Logging in: 

def login():
    global owner
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)            # creating UDP type socket
        sock.connect(("18.195.107.195",  5378))                             # connecting socket to server

        name = input("Show me the ID!!! ")                                  # getting name of the user logged in
        owner = name
        sock.sendall(bytes("HELLO-FROM {}\n".format(name), "utf-8"))        # Sending name to server for it to be displaed
                     
        data = sock.recv(4096).decode("utf-8")                              # getting data from server and decoding it

        if data == "IN-USE\n":                                              # If user name is already taken
            print("username is taken,Try again: ")
        elif data == "BUSY\n":                                              # if the server is busy and cannot respond at moment
            print("The server is full.")
        else:  
            print("Hello")
            break

        sock.close()                                                        # closing socket connection       
    return sock


# Function to convert String to Binary sequence

def string_to_binary(s):
    res = ''
    for c in s:
        bin_ = str(format(ord(c), 'b'))             # converting each letter to binary sequence
        bin_ = '0'*(8 - len(bin_)) + bin_           # appending extra '0's for padding
        res = res + bin_
    return res


# Function to convert Binary sequence to String

def binary_to_string(s):
    return ''.join([chr(int(s[i:i + 8], 2)) for i in range(0, len(s), 8)])      # each set of 8 bits are converted to integer value and then to their corresponding ASCII character value and appende to string


# Function to XOR binary strings 

def xor(a, b): 
    result = [] 
   
    for i in range(1, len(b)): 
        if a[i] == b[i]:            # if the i-th character is same then '0'
            result.append('0') 
        else:                       # otherwise '1'
            result.append('1') 
   
    return ''.join(result)          # append all result together in a string
   
   
# Performs Modulo-2 division 

def mod2div(divident, divisor):  
    pick = len(divisor) 
    tmp = divident[0 : pick]                                # 1st len(divisor) number of characters from divident
   
    while pick < len(divident):                             # if the size of divisor > current divident then division cannot proceed
        if tmp[0] == '1':                                   # if 1st character of tmp is '1': normal division modulo 2
            tmp = xor(divisor, tmp) + divident[pick] 
   
        else:                                               # otherwise use padding before division modulo 2
            tmp = xor('0'*pick, tmp) + divident[pick] 
        pick += 1

    #concatinate the remainder to the divident
    if tmp[0] == '1': 
        tmp = xor(divisor, tmp) 
    else: 
        tmp = xor('0'*pick, tmp) 
   
    checkword = tmp 
    return checkword 

   
# Encode the original data with error detection redundant bits

def encodeData(data): 
    data = string_to_binary(data)                   # convert the message to binary 1st
    l_key = len(msg_key) 
    appended_data = data + '0'*(l_key-1)            # concatinate tailing '0's of divident
    remainder = mod2div(appended_data, msg_key)     # encoding the message with redundant bits
   
    codeword = data + remainder                     # appending redundant bits to message bits
    return codeword


# Decode the encoded message to get the original message

def decodeData(data): 
    l_key = len(msg_key) 
    temp = "0" * (l_key - 1)
    appended_data = data + temp 
    remainder = mod2div(appended_data, msg_key)     # decoding the message to get remainder bits
   
    if remainder == temp:                           # if remainder is zero then probably no error
        return False
    else:
        return True                                 # otherwise guarenteed error exits


# Function to resend the message whose ACK has not been recieved:

def resend_message(username, pkt_no, message):
    if username not in ack_list.keys():                                             # Initializing list if not initialized
        ack_list[username] = []

    if pkt_no not in ack_list[username]:                                            
        print("Message {} to {} not sent...Resending".format(pkt_no, username))
        send_packet(username, message, pkt_no)                                      # Scheduling message delivery by inserting the message into message queue


# Function to store and send the message packets with proper sequence number

def send_packet(username, message, pkt_no = 0):
    global sender_packet, message_queue

    if username not in sender_packet.keys():                # Initializing the last packet number sent for 'username'
        sender_packet[username] = 0

    if pkt_no == 0:                                         # If no packet number provided use the contnuing seq number for the user
        sender_packet[username] += 1
        pkt_no = sender_packet[username]

    message_to_send = "{}:{}".format(pkt_no, message)       # Packing the message and sequence number together
    bin_message = encodeData(message_to_send)               # Encode the message into binary and then into CRC format
    message_queue.append((username, bin_message))           # Schedule the message for delivary

    print("Sending message...") 

    if message_queue:
        t = threading.Timer(delay, resend_message, args = (username, pkt_no, message))                  # Initialize timer
        sock.sendall(bytes("SEND {} {}\n".format(message_queue[0][0], message_queue[0][1]),"utf-8"))    # Sending the top packet in the queue
        t.start()                                                                                       # start timer for getting ACK
        message_queue = message_queue[1:]                                                               # Popping the 1st packet from queue


# Function to recieve packets from user and storing them in buffer

def receiver():
    global buff

    while True:
        message = sock.recv(4096).decode("utf-8")           # getting the packet from server

        while message.find("\n") == -1:                     # if packet doesnot contains trailing message delimiter ('\n') 
            message += sock.recv(4096).decode("utf-8")      # then keep on recieving and appeng message to current message

        messageArr = message.splitlines()                   # split the message segments based on '\n' character
        for i in range(len(messageArr)):                    # Insert the set of messages into buffer
            if messageArr[i]:
                buff.append(messageArr[i])
        

# Process Each message packet in the buffer

def checkmsg():
    global reciever_packet, last_print, ack_list
    i = 0                                                                   # Pointer to current buffer message

    while True:
        if i < len(buff):
            curr_buff = buff[i]
            if curr_buff == "SEND-OK":                                      # if message has left server
                print("Message has been sent by server")                    
                i += 1
                
            elif curr_buff == "UNKNOWN":                                    # if user has logged out
                print("User not logged in")
                i += 1
                
            elif "WHO-OK" in curr_buff:                                     # gets all the users who are currently online
                print(f"People online: {curr_buff[6:]}", end="")
                i += 1
                
            elif curr_buff == "BAD-RQST-HDR":                               # if header format is not correct
                print("Error in the header of the message")
                i += 1
                
            elif curr_buff == "BAD-RQST-BODY":                              # if message format is not correct
                print("Error in the body of the message")
                i += 1
                
            elif "DELIVERY" in curr_buff:                                   # if message has arrived from some user
                messageParts = curr_buff.split(" ")                         # dividing message parts into suitable variables based on message format
                messageParts = messageParts[1:]                             # removing "DELIVERY" keyword from list
                userName = messageParts[0]                                  # getting username from message

                error = decodeData(messageParts[1])                         # decode the encoded message part in the packet to check for error(s)

                if error:                                                   # if error is present in message no "ACK" sent back
                    print("Message contain Errors!!!")
                    i += 1
                    continue                                                # continue looping

                messageParts = binary_to_string(messageParts[1][:-(len(msg_key) - 1)]).split(' ')       # if no error present, convert the original message part (removing the redundant bits) to set of characcters from binary stream

                if messageParts:                                            # if list of message is not empty
                    if 'ACK' == messageParts[0]:                            # chek if the message is actually an Acknowledgment
                        seq = messageParts[1].split(':')[-1]                # get the sequence number of the ACK
                        seq = int(seq)

                        if userName not in ack_list.keys():                 # initializing list of ACK for a particular username
                            ack_list[userName] = []

                        if seq in ack_list[userName]:                       # if ACk number already present in list for the user, then the message ACk has been delayed
                            print('Delayed response recieved from {} for message number {}'.format(userName, seq))
                            i += 1
                            continue                                        # so don't proceed any further and continue looping 

                        ack_list[userName].append(seq)                      # append ACK number to the list of ACks for the user
                        print('Your message number {} to {} has been successfully recieved\n'.format(seq, userName))

                        i += 1
                        continue                                            # don't proceed any further and continue looping
                    
                    seq_num, message = messageParts[0].split(":")           # get the sequence number and the 1dt message part
                    for idx in range(1, len(messageParts)):                 # if more messages are present, keep concatinating them
                        message += ' ' + messageParts[idx]

                    if userName not in reciever_packet.keys():              # initializing recieved packet list for the user
                        reciever_packet[userName] = []

                    reciever_packet[userName].append((int(seq_num), message)) # appending recieved packet list for the user

                    if userName not in last_print.keys():                   # initializing the last message number printed for the user
                        last_print[userName] = 0

                    if (last_print[userName] + 1) in [int(x[0]) for x in reciever_packet[userName]]:    # if nest message number already recieved 
                        last_print[userName] += 1
                        curr = last_print[userName]
                        reciever_packet[userName].sort(key = lambda x: (int(x[0])))
                        while curr in [int(x[0]) for x in reciever_packet[userName]]:                   # loop for correponding message number until next sequencenumber not found
                            print("{}: {}".format(userName, reciever_packet[userName][curr-1][1]))
                            msg_to_send = "ACK @{}:{}".format(owner, curr)                              # the message sent back on getting a message is ACK along with reciever name and sequence number
                            bin_message = encodeData(msg_to_send)                                       # encode the message
                            sock.sendall(bytes("SEND {} {}\n".format(userName, bin_message), 'utf-8'))  # send the message without timer this time
                            curr += 1

                    i += 1
                   




t1 = threading.Thread(target=receiver, daemon=True)         # Thread1 to continously recieve packets
t2 = threading.Thread(target=checkmsg, daemon=True)         # Thread2 to continously process any remaining packets in buffer

sock = login()
t1.start()
t2.start()

# def sender():
while True:
    userInput = input("> ")
    if userInput == "":
        continue
    
    if userInput == "!quit":
        sock.close()
        break
        
    elif userInput == "!who":
        sock.sendall(bytes("WHO\n","utf-8"))

    elif userInput[0] == '@':
        space = userInput.find(' ')
        username = userInput[1 : space]
        message = userInput[space+1 : ]
        send_packet(username, message)

    else:
        print("userinput not recognised.")
        continue