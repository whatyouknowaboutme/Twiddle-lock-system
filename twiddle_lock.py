#!/usr/bin/python

#imports required
import RPi.GPIO as GPIO
import Adafruit_MCP3008
import time
import os
import spidev
import sys
import datetime
import subprocess as sp
from timeit import default_timer as timer
import numpy as np
import signal
import pygame


#global variables
twiddle_position =0 #variable to store current twiddle lock position 
twiddle_position_prev=-30000 #variable to keep track for previous twiddle position
adc_value_array=[0] #array to store all log twiddle_positions from the MCP3008
timer_array =[0] #array to store all the log times in which were taken when the twiddle positions were logged
begin_time=0 #start the timer when Sline is pressed
i = 0 #variable used to store the time, when a twiddle is in one position for more than one sample
time_s=[0] #store the times in which L and R were stored in direction_sequence[]
check_state=0 #variable used in-part to detect when twiddle_position has been in one position for 1 second -> for when twiddle position goes in the same direction as the previous twiddle position
direction_sequence =[-1] #array used to store the sequence of Left and Right by definition: left = 0 and right =1
secure_unsecure=0 #used to toggle between unsecure and secure mode
code=[1,1,0] #hardcoded combination
code_time=[1.0433349609375,1.035263967514038,1.5382449626922607] #timing requiredments for thw above hardcoded combination
Lock_state=1 #used to track where the lock is locked or unlocked -> at startup its locked
sline_pressed=0
###############################################################################################
#					SPI SETUP					      #
###############################################################################################
#Set pin definitions for SPI								      #
SPICLK=11										      #
SPIMISO = 9										      #
SPIMOSI = 10										      #
SPICS = 8										      #
											      #
											      #
mcp = Adafruit_MCP3008.MCP3008(clk=SPICLK, cs=SPICS, mosi=SPIMOSI, miso=SPIMISO)	      #
											      #
###############################################################################################


###############################################################################################
#                                       	MAIN					      #
###############################################################################################
def main ():
	try:
		# initialization of ADC and pushbuttons
		GPIO.setmode(GPIO.BCM) 
		init_pushbuttons() #intialize pushbuttons
		init_event_detect() #intialize interuppts for pushbuttons
		init_LEDs() #initalize LEDs for U-Line and L-Line simulation
		pygame.init() #intialize audio playback

		#intialise spi
		init_spi(SPIMOSI,SPIMISO,SPICLK,SPICS)
		mcp = Adafruit_MCP3008.MCP3008(clk=SPICLK, cs=SPICS, mosi=SPIMOSI, miso=SPIMISO)

		global sline_pressed #used for start of program when system is idle
		
		while(True): #infinite loop
			if (sline_pressed>=1):
				Dial() #THIS is Twiddle_dAtA LOGGER IN my report for the various diagram!!!
	except KeyboardInterrupt:
		GPIO.cleanup()
	GPIO.cleanup()


#initialization of SPI for communication to  ADC
def init_spi(SPIMOSI, SPIMISO, SPICLK,SPICS):
	GPIO.setup(SPIMOSI, GPIO.OUT)
	GPIO.setup(SPIMISO, GPIO.IN)
	GPIO.setup(SPICLK, GPIO.OUT)
	GPIO.setup(SPICS, GPIO.OUT)

#initalise input mode for push button s_line
def init_pushbuttons():
	GPIO.setup(19, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#initalise output LEDs for L-Line and U-Line
def init_LEDs():
	GPIO.setup(21, GPIO.OUT)
 	GPIO.setup(20, GPIO.OUT)
	GPIO.output(21, False)
	GPIO.output(20, True)
	time.sleep(2)
	GPIO.output(20,False)

#intialise event detection/interrupts for s_line/pushbuttion
def init_event_detect():
	GPIO.add_event_detect(19,GPIO.FALLING,S_Line ,bouncetime=300)

#when S_line badically everything resets
def S_Line (channel):
	global begin_time, adc_value_array,mcp,timer_array,i,direction_sequence,check_state,time_s,sline_pressed
	print("Sline pressed, reset!!")
	#print(direction_sequence) #debug 
 	#print(adc_value_array) #debug reasons
#	print(time_s)	#debug reasons

	begin_time =timer()
	timer_array=[0]
	adc_value_array=[mcp.read_adc(0)]
	direction_sequence=[-1]
	i=0
	check_state=0
	sline_pressed=1
	time_s=[]


def Dial():
	global twiddle_position_prev, twiddle_position, adc_value_array,mcp,i,direction_sequence,check_state,time_s
	
	twiddle_position=mcp.read_adc(0) #get current twiddle position
	time.sleep(0.01) #sampling time for twiddle_positon

	#print(twiddle_position_prev) #debug
	#print(abs(twiddle_position-twiddle_position_prev)) #debug

	if (abs(twiddle_position-twiddle_position_prev)<10): #check if twiddle_positon has remained in one position
		timer_array[-1]=timer()-begin_time #store for how long has it been in this position

		if ((adc_value_array[-1]-twiddle_position)<0 and direction_sequence[-1]==0): #check if the twiddle_positon moved in opposite direction from the last sample (therefore counts as right)
			direction_sequence.append(1) #append "Right" to the sequence of inputs 
			time_s.append(timer()-begin_time) #append the time @ which this value was stored
			print("I have detected right ie. going opposite") #debug 
		else:
			if ((adc_value_array[-1]-twiddle_position)>0 and direction_sequence[-1]==1): 
                        	direction_sequence.append(0) #check if the twiddle_positon move in the opposite direction from the previous sampled twiddle position (ie its going left)
				time_s.append(timer()-begin_time) #append the time @ which this value was stored
				print("I have detected left ie. going opposite") #debug
		if (i==0): #if twiddle position has remained in one position for more than one sample
                        i=timer_array[-1] #store the last time it was sample in the case that it changed in the same direction as it was moving before  
			check_state=0 #reset check_state
		#print (timer_array[-1]-i) #debug
			
		if(timer_array[-1]-i>=3): # if more than 3 seconds had gone by than user is done entering code 
			check_code() #call check code
	else:
		if(((timer_array[-1]-i)<=2) and ((timer_array[-1]-i) >=1)): #for the case when user moves the twiddle position in the same direction after just 1 second but less than 2 seconds
			i=0 #reset i=0 because not on the twiddle_position anymore
		#	print(timer_array[-1]) #debug
		#	print(i) #debug
			if ((adc_value_array[-1]-twiddle_position>0) and check_state==0): #check  to see if going left
				if(direction_sequence[-1]==-1): #used for starting sequence when the first motion of s_line has been pressed
					direction_sequence[-1]=0 #overite the default value to state 'left'
					time_s.append(timer()-begin_time) #store the time in which this took place
					print("first stored value: left") #debug
				else:
					if (direction_sequence[-1]==0): #check if the prior value is left too, and if it is then it must be going in the same direction
						print("left again!") #debug
						time_s.append(timer()-begin_time) #store time in which this took place
						direction_sequence.append(0) #append the code sequence ie. 'Left'
				check_state=1 #check_state updated so this event can trigger until twiddle_state is in still again

			else:
				if ((adc_value_array[-1]-twiddle_position<0) and check_state==0): #same as before but for right sequence only
					if(direction_sequence[-1]==-1):
						direction_sequence[-1]=1
						time_s.append(timer()-begin_time)
						print("first stored valeu: right") #debug
					else:
                                       		if (direction_sequence[-1]==1):
                                               		print("right again!") #debug
							time_s.append(timer()-begin_time)
                                               		direction_sequence.append(1)
					check_state=1

		adc_value_array.append(twiddle_position) #store twiddle positions in array for anlaysis 
		timer_array.append(timer()-begin_time) #store times of all values obtained when twiddle position was moved by each sample
		
	twiddle_position_prev=twiddle_position #store into previous position

#check_cod is the equivalent to check_data in the report!!!!!!!!!
def check_code(): #used to check if combintion is correct
	global direction_sequence,secure_unsecure,Lock_state
	if (secure_unsecure==1): #secure_mode =1 and unsecure mode =0
		print ("In secure mode now:\n\n")
		print("combination entered:")
		print (direction_sequence)
		sort()
		if((np.array_equal(direction_sequence,code)==True) and check_times()==True): #combination and Time must be in correct order
			print("combination correct")
			correct_code()
			if (Lock_state==1): #if locked then it must unlock
				unlock()
			else: #if unlocked then it must lock
				lock()
		else: #if code is incorrect 
			incorrect_code()

	else: #if in unsecure mode
		print("In unsecure mode now:\n\n")
		print("combination entered:")
		print (direction_sequence)

		sort() #sort the times
		if(check_times()==True): #if correct
			correct_code() 
			if (Lock_state==1): #if locked must unlock
				unlock() 
			else: #if unlokced then lock
				lock()
		else: #if incorrect
			incorrect_code()

	while(GPIO.input(19)==True): #do do anything until s_line is triggered again
		True

#sort function
def sort():
	global secure_unsecure
	if (secure_unsecure==0):
		print("sorting...\n\n")
		print("Unsorted times: ")
	for i in range (1,len(time_s)):
		time_s[i]-=time_s[i-1]
	print (time_s)
	time_s.sort()
	if (secure_unsecure==0):
		print("sorted\n\n")
		print ("sorted times:")
		print (time_s)
	#print(time_s) #debug

def check_times(): #check id time corresponds
	count=0
	print("checking if times correct...\n\n")
	#print("checcking....") #debug
	if (len(time_s)!=3):
	#	print("FALSE") #debug
		return False
	else:
	#	print("True") #debug
		print("The delta times are as follows:")
		for i in range (len(code_time)):
			print(abs(time_s[i]-code_time[i]))
			if (abs(time_s[i]-code_time[i])<0.5):
				count+=1
		print ('{:d} of the times were corrext\n\n'.format(count))
		if(count==3):
			return True

def unlock():
	print ("unlocking...\n\n")
	global Lock_state
	GPIO.output(21, True)                 
	time.sleep(2)
	print ("waited 2 seconds\n\n")                                
	GPIO.output(21, False)
	print("unlocked\n\n")
        direction_sequence=[-1]
        sline_pressed=0
        Lock_state=0

def lock ():
	print ("locking...\n\n")
        global Lock_state
        GPIO.output(20, True)
        time.sleep(2)
	print ("waited 2 seconds\n\n")
        GPIO.output(20, False)
	print ("locked\n\n")
        direction_sequence=[-1]
        sline_pressed=0
        Lock_state=1

def incorrect_code():
	print ("The code is incorrect, playing sound\n\n")
	pygame.mixer.init() #audio
        pygame.mixer.music.load("crap.wav") #audio
        pygame.mixer.music.play() #audiopygame.mixer.init() #audio

def correct_code():
	print ("The code is correct, playing sound\n\n")
	pygame.mixer.init() #audio purpose
        pygame.mixer.music.load("mburger.wav") #audio purpose
        pygame.mixer.music.play() #audio purpose

if __name__ == '__main__':
	main()



