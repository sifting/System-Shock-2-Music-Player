from struct import unpack
import sys

#This is annoying but pydub is the only library that can load
#these file types somewhat properly
from pydub import AudioSegment
		
class Sample:
	def __init__ (self, filename):
		self.filename = 'SONGS/' + filename
		self.data = AudioSegment.from_file (self.filename)\
		.set_frame_rate (44100)\
		.set_sample_width (2)\
		.set_channels (2)

class Jump:
	def __init__ (self, destination, probability):
		self.dst = destination
		self.prob = probability

class Event:
	def __init__ (self, type, flags):
		self.type = type
		self.flags = flags
		self.jumps = []
		
	def add_jump (self, jump):
		self.jumps.append (jump)
		
	def jump (self):
		import random
		x = random.randint (0, 100)
		total = 0
		for i in range (len (self.jumps)):
			#Shuffle the list into a random order
			#This step improves diversity in the selection
			shuffled = random.randint (i, len (self.jumps) - 1)
			swap = self.jumps[i]
			self.jumps[i] = self.jumps[shuffled]
			self.jumps[shuffled] = swap
			#Without the above shuffle equiprobable options have predictable
			#selections, even though they should be random
			jump = swap
			total += jump.prob
			if x <= total:
				return jump.dst
		#Always a safe choice, and should never really get here anyway
		return 0

class Section:
	def __init__ (self, name, volume, loopcount):
		self.name = name
		self.vol = volume
		self.loopcount = loopcount
		self.samples = []
		self.events = {}

	def add_sample (self, sample):
		self.samples.append (sample)
		
	def get_sample (self, index):
		return self.samples[index]
		
	def add_event (self, event):
		self.events[event.type] = event
		
	def get_event (self, type):
		if type not in self.events:
			return None
		return self.events[type]

class Song:
	def __init__ (self, title):
		self.title = title
		self.sects = []
	def add_section (self, section):
		self.sects.append (section)
	def get_section (self, index):
		return self.sects[index]

def load_song (file):
	with open (file, 'rb') as snc:
		#Should always be 1
		version = unpack ('<l', snc.read (4))[0]
		if version != 1:
			print ("Misery and woe! The file version is not correct!")
			return None
		#Song title
		title = unpack ('<32s', snc.read (32))[0]\
			.split (b'\x00')[0]\
			.decode ('utf-8')
		print ("Title: {}".format (title))
		song = Song (title)
		
		#Always zero?
		unknown = unpack ('<l', snc.read (4))[0]
		print ("Unknown: {}".format (unknown))

		nsections = unpack ('<l', snc.read (4))[0]
		for i in range (nsections):
			name = unpack ('<32s', snc.read (32))[0]\
				.split (b'\x00')[0]\
				.decode ('utf-8')
			vol, loop = unpack ('<ll', snc.read (8))
			print (
				"Section {}: name = '{}', vol = {}, loop count = {}"
				.format (i, name, vol, loop)
			)
			section = Section (name, vol, loop)
			
			#In theory each section may have multiple samples, but usually
			#they just seem to have one?
			nsamples = unpack ('<l', snc.read (4))[0]
			for j in range (nsamples):
				name = unpack ('<32s', snc.read (32))[0]\
					.split (b'\x00')[0]\
					.decode ('utf-8')
				print ("\tSample {}: name = '{}'".format (j, name))
				sample = Sample (name)
				section.add_sample (sample)
				
			#Events are the stimuli that makes the song dynamic. Each event
			#may have one or more jump to another section with a probability
			#of it being taken
			nevents = unpack ('<l', snc.read (4))[0]
			for j in range (nevents):
				#Read out type name and flags - which are always zero?
				name = unpack ('<32s', snc.read (32))[0]\
					.split (b'\x00')[0]\
					.decode ('utf-8')
				flags = unpack ('<l', snc.read (4))[0]
				print ("\tEvent: name = '{}', flags = {}"\
					.format (name, flags))
				event = Event (name, flags)
				
				#Read out the jumps to other sections
				njumps = unpack ('<l', snc.read (4))[0]
				for k in range (njumps):
					dst, prob = unpack ('<ll', snc.read (8))
					print (
						"\t\tJump: destination = {}, probability = {}"
						.format (dst, prob)
					)
					jump = Jump (dst, prob)
					event.add_jump (jump)
				
				#Store event into the section
				section.add_event (event)
			
			#Store section into song
			song.add_section (section)
		#Perfect!
		return song
	#No joy!
	return None

class Player:
	def __init__ (self):
		self.play (None)

	def play (self, song):
		self.song = song
		self.event = ''
		self.prio =-1
		self.prev =-1
		self.curr = 0
		self.next = 0
		self.seek = 0
		self.signal ('theme begin', 1)
	
	def signal (self, event, priority):
		#Ensure there is a song
		if self.song is None:
			return
		#Ignore lower priority signals
		if priority < self.prio:
			return
		#Save the event info here
		#This keeps the event raised until a section can reply to it
		self.event = event
		self.prio = priority
		#Ensure this section can respond to the signal
		sect = self.song.get_section (self.curr)
		if None is sect:
			return
		ev = sect.get_event (self.event)
		if None is ev:
			return
		#Set the next section to play
		self.next = ev.jump ()
		#Try to break up repeat phrases
		if self.next == self.curr or self.next == self.prev:
			self.next = ev.jump ()
		#Clear the signal
		self.event = ''
		self.prio = -1
	
	def on_start (self):
		#Advance the song
		self.prev = self.curr
		self.curr = self.next
		#Send default event to keep things going
		self.signal ('', 0)
		print (self.event)
		
_player = Player ()
_song = load_song (sys.argv[1])
_player.play (_song)


import pyaudio
def callback(in_data, frame_count, time_info, status):
	global _player
	#2 channels, 2 byte width samples
	amt = 4*frame_count
	
	#Let the player know a new sample has started
	if _player.seek < amt:
		_player.on_start ()
		#Print current sample
		n = _player.song.get_section (_player.curr).get_sample (0).filename
		if 'SONGS/empty.wav' != n:
			print (n)
	
	#Grab the sample data
	curr = _player.song.get_section (_player.curr)\
		.get_sample (0).data.raw_data
	next = _player.song.get_section (_player.next)\
		.get_sample (0).data.raw_data
	
	#Read the next chunk from the current sample
	chunk = curr[_player.seek : _player.seek + amt]
	
	#See if we need to read from the next sample too
	#this happens toward the end of the current sample,
	#when there is not enough data left to fill the request
	length = len (chunk)
	if length < amt:
		frac = amt - length
		chunk += next[:frac]
		_player.seek = frac
	else:
		_player.seek += amt
	
	#Let pyaudio do its thing
	return (chunk, pyaudio.paContinue)
	
#Create a new pyaudio stream and install our callback
p = pyaudio.PyAudio ()
stream = p.open (
	format=pyaudio.paInt16, channels=2, rate=44100,
	output=True,
	stream_callback=callback
)

#Stream until the user gets bored
stream.start_stream ()
while stream.is_active():
	cmd = input ()
	if "quit" == cmd:
		break
	_player.signal ("theme " + cmd, 10)

#Clean up pyaudio
stream.stop_stream ()
stream.close ()
p.terminate ()
