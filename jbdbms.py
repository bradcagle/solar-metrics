#!/usr/bin/env python3
from bluepy.btle import Peripheral, DefaultDelegate, BTLEException
import struct
import argparse
import sys
import time
import binascii
import atexit
import mysql.connector



class JBDParser(DefaultDelegate):

	def __init__(self, database, db_table, db_user, db_pass):
		DefaultDelegate.__init__(self)

		self.database = database
		self.db_table = db_table
		self.db_user = db_user
		self.db_pass = db_pass

		# Basic info part 1 data
		self.freshBasicInfo1 = False
		self.volts, self.amps, self.capacity, self.remaining, self.watts, self.cycles = (0.0, 0.0, 0.0, 0.0, 0.0, 0)
		self.b16, self.b15, self.b14, self.b13 = (0, 0, 0, 0)
		self.b12, self.b11, self.b10, self.b09 = (0, 0, 0, 0)
		self.b08, self.b07, self.b06, self.b05 = (0, 0, 0, 0)
		self.b04, self.b03, self.b02, self.b01 = (0, 0, 0, 0)

		# Basic info part 2 data
		self.freshBasicInfo2 = False
		self.vers, self.percent, self.cells, self.tempsensors = (0,0,0,0)
		self.temp1, self.temp2, self.temp3, self.temp4 = (0,0,0,0)

		# Cell voltages part 1
		self.freshCellVoltage1 = False
		self.cv1, self.cv2, self.cv3, self.cv4, self.cv5, self.cv6, self.cv7, self.cv8 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

		# Cell voltages part 2
		self.freshCellVoltage2 = False
		self.cv9, self.cv10, self.cv11, self.cv12, self.cv13, self.cv14, self.cv15, self.cv16 = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


	def writeDB(self):

		db = None
		try:
			# Connect to database
			db = mysql.connector.connect(host='localhost', database=self.database, user=self.db_user, password=self.db_pass)
			if db.is_connected():
				cursor = db.cursor()

				query = "INSERT INTO %s SET volts=%0.2f, amps=%0.2f, watts=%0.2f, capacity=%0.2f, remaining=%0.2f, cycles=%i, " % (self.db_table, self.volts, self.amps, self.watts, self.capacity, self.remaining, self.cycles)
				query += "percent=%i, cells=%i, tempsensors=%i, temp1=%0.2f, temp2=%0.2f, temp3=%0.2f, temp4=%0.2f, " % (self.percent, self.cells, self.tempsensors, self.temp1, self.temp2, self.temp3, self.temp4)
				query += "cv1=%0.3f, cv2=%0.3f, cv3=%0.3f, cv4=%0.3f, cv5=%0.3f, cv6=%0.3f, cv7=%0.3f, cv8=%0.3f, " % (self.cv1, self.cv2, self.cv3, self.cv4, self.cv5, self.cv6, self.cv7, self.cv8)
				query += "cv9=%0.3f, cv10=%0.3f, cv11=%0.3f, cv12=%0.3f, cv13=%0.3f, cv14=%0.3f, cv15=%0.3f, cv16=%0.3f;" % (self.cv9, self.cv10, self.cv11, self.cv12, self.cv13, self.cv14, self.cv15, self.cv16)
				#print(query)
				cursor.execute(query)
				#record = cursor.fetchone()
				db.commit()

		except Error as e:
			print("Error while connecting to MySQL", e)

		finally:
			if db and db.is_connected():
				cursor.close()
				db.close()


	def basicInfo1(self, data):
		volts, amps, remaining, capacity, self.cycles, mdate, balance1, balance2 = struct.unpack_from('>HhHHHHHH', data, 4) #Skip first 4 header bytes

		self.volts, self.amps, self.capacity, self.remaining, self.watts  = (volts/100, amps/100, capacity/100, remaining/100, (volts/100)*(amps/100))

		bal1 = (format(balance1, "b").zfill(16))
		self.b16, self.b15, self.b14, self.b13 = (int(bal1[0:1]), int(bal1[1:2]), int(bal1[2:3]), int(bal1[3:4]))
		self.b12, self.b11, self.b10, self.b09 = (int(bal1[4:5]), int(bal1[5:6]), int(bal1[6:7]), int(bal1[7:8]))
		self.b08, self.b07, self.b06, self.b05 = (int(bal1[8:9]), int(bal1[9:10]), int(bal1[10:11]), int(bal1[11:12]))
		self.b04, self.b03, self.b02, self.b01 = (int(bal1[12:13]), int(bal1[13:14]), int(bal1[14:15]), int(bal1[15:16]))

		print("Volts: %0.2f" % self.volts)
		print("Amps: %0.2f" % self.amps)
		print("Watts: %0.2f" % self.watts)
		print("Remaining: %0.2f" % self.remaining)
		print("Capacity: %0.2f" % self.capacity)
		print("Cycles: %0i" % self.cycles)
		print("Balancing: %0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i,%0i" % (self.b01,self.b02,self.b03,self.b04,self.b05,self.b06,self.b07,self.b08,self.b09,self.b10,self.b11,self.b12,self.b13,self.b14,self.b15,self.b16))

		self.freshBasicInfo1 = True


	def basicInfo2(self, data):
		# fet 0011 = 3 both on ; 0010 = 2 disch on ; 0001 = 1 chrg on ; 0000 = 0 both off

		protect, self.vers, self.percent, fet, self.cells, self.tempsensors = struct.unpack_from('>HBBBBB', data, 0)

		# Unpack temp sensors
		if self.tempsensors == 4: # 4 temp sensors
			temp1, temp2, temp3, temp4, b77 = struct.unpack_from('>HHHHB', data, 7)
			self.temp1, self.temp2, self.temp3, self.temp4 = ((temp1-2731)/10, (temp2-2731)/10, (temp3-2731)/10, (temp4-2731)/10)
		elif self.tempsensors == 3: # 3 temp sensors
			temp1, temp2, temp3, b77 = struct.unpack_from('>HHHB', data, 7)
			self.temp1, self.temp2, self.temp3 = ((temp1-2731)/10, (temp2-2731)/10, (temp3-2731)/10)
		elif self.tempsensors == 2: # 2 temp sensors
			temp1, temp2, b77 = struct.unpack_from('>HHB', data, 7)
			self.temp1, self.temp2 = ((temp1-2731)/10, (temp2-2731)/10)
		elif self.tempsensors == 1: # 1 temp sensors
			temp1, b77 = struct.unpack_from('>HB', data, 7)
			self.temp1 = (temp1-2731)/10

		prt = (format(protect, "b").zfill(16))	# protect trigger (0,1)(off,on)
		ovp = int(prt[0:1])			# single cell overvoltage
		uvp = int(prt[1:2])			# single cell undervoltage
		bov = int(prt[2:3])			# battery overvoltage
		buv = int(prt[3:4])			# battery undervoltage
		cot = int(prt[4:5])			# current over temp
		cut = int(prt[5:6])			# current under temp
		dot = int(prt[6:7])			# discharge over temp
		dut = int(prt[7:8])			# discharge under temp
		coc = int(prt[8:9])			# charge over current
		duc = int(prt[9:10])			# discharge under current
		sc = int(prt[10:11])			# short circuit
		ic = int(prt[11:12])			# ic failure
		cnf = int(prt[12:13])			# fet config problem
		print("ovp:%0i uvp:%0i bov:%0i buv:%0i cot:%0i cut:%0i dot:%0i dut:%0i coc:%0i duc:%0i sc:%0i ic:%0i cnf:%0i " % (ovp,uvp,bov,buv,cot,cut,dot,dut,coc,duc,sc,ic,cnf))

		print("protect:%0000i percent:%00i fet:%00i cells:%0i tempsensors:%0i temp1:%0.1f temp2:%0.1f temp:%0.1f temp4:%0.1f" % (protect,self.percent,fet,self.cells,self.tempsensors,self.temp1,self.temp2,self.temp3,self.temp4))

		self.freshBasicInfo2 = True


	def cellVoltage1(self, data):
		cv1, cv2, cv3, cv4, cv5, cv6, cv7, cv8 = struct.unpack_from('>HHHHHHHH', data, 4) #Skip first 4 header bytes

		# Convert cell voltages to float
		self.cv1, self.cv2, self.cv3, self.cv4, self.cv5, self.cv6, self.cv7, self.cv8 = (cv1/1000, cv2/1000, cv3/1000, cv4/1000, cv5/1000, cv6/1000, cv7/1000, cv8/1000)

		print("Cell voltages 01:%0.3f 02:%0.3f 03:%0.3f 04:%0.3f 05:%0.3f 06:%0.3f 07:%0.3f 08:%0.3f" % (self.cv1, self.cv2, self.cv3, self.cv4, self.cv5, self.cv6, self.cv7, self.cv8))

		self.freshCellVoltage1 = True


	def cellVoltage2(self, data):
		cv9, cv10, cv11, cv12, cv13, cv14, cv15, cv16, b77 = struct.unpack_from('>HHHHHHHHB', data, 0)

		# Convert cell voltages to float
		self.cv9, self.cv10, self.cv11, self.cv12, self.cv13, self.cv14, self.cv15, self.cv16 = (cv9/1000, cv10/1000, cv11/1000, cv12/1000, cv13/1000, cv14/1000, cv15/1000, cv16/1000)

		print("Cell voltages 09:%0.3f 10:%0.3f 11:%0.3f 12:%0.3f 13:%0.3f 14:%0.3f 15:%0.3f 16:%0.3f" % (self.cv9, self.cv10, self.cv11, self.cv12, self.cv13, self.cv14, self.cv15, self.cv16))

		# Cells min, max and delta
		allcells = [self.cv1, self.cv2, self.cv3, self.cv4, self.cv5, self.cv6, self.cv7, self.cv8, self.cv9, self.cv10, self.cv11, self.cv12, self.cv13, self.cv14, self.cv15, self.cv16]
		cellsmin = min(allcells)
		cellsmax = max(allcells)
		delta = cellsmax-cellsmin
		mincell = (allcells.index(min(allcells))+1)
		maxcell = (allcells.index(max(allcells))+1)
		print("mincell,cellsmin,maxcell,cellsmax,delta\r\n%i,%0.3f,%i,%0.3f,%0.3f" % (mincell,cellsmin,maxcell,cellsmax,delta))

		self.freshCellVoltage2 = True


	def handleNotification(self, cHandle, data):
		hex_data = binascii.hexlify(data)
		hex_string = hex_data.decode('utf-8')
		#print(hex_string)

		# Route incoming BMS data to the appropriate parser
		if hex_string.find('dd04') != -1:
			self.cellVoltage1(data)
		elif hex_string.find('77') != -1 and len(data) == 19:	 # x04
			self.cellVoltage2(data)
		elif hex_string.find('77') != -1 and len(data) == 3:
			self.freshCellVoltage2 = True # Just fake that we have cellVoltage2. 8s BMS still sends this but it's short like only 3 bytes. Anyhow by faking it we can staisfy our test for full set of fresh data
		elif hex_string.find('dd03') != -1:
			self.basicInfo1(data)
		elif hex_string.find('77') != -1 and len(data) < 19 and len(data) > 3:	 # x03 len 36 for 4 temps, 32 for 3 temps, 28 for 2
			self.basicInfo2(data)

		# If we've got a full set of fresh data from the BMS write it to the database
		if self.freshBasicInfo1 and self.freshBasicInfo2 and self.freshCellVoltage1 and self.freshCellVoltage2:
			self.writeDB()
			self.freshBasicInfo1 = False
			self.freshBasicInfo2 = False
			self.freshCellVoltage1 = False
			self.freshCellVoltage2 = False




# Grab command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--address", help="BT Address", required=True)
parser.add_argument("-i", "--interval", nargs="?", default=30, type=int, help="Interval", required=False)
parser.add_argument("-d", "--db", nargs="?", default="solar", help="Database name", required=False)
parser.add_argument("-t", "--dbtable", nargs="?", default="bms", help="Database table", required=False)
parser.add_argument("-u", "--dbuser", nargs="?", default="root", help="Database user", required=False)
parser.add_argument("-p", "--dbpass", help="Database password", required=True)
args = parser.parse_args()


# Connect to BMS
try:
	print('Connecting to BMS')
	bt = Peripheral(args.address, addrType="public")
except BTLEException as ex:
	time.sleep(10)
	bt = Peripheral(args.address, addrType="public")
except BTLEException as ex:
	print('Connection failed')
	exit()
else:
	print('Connected ', args.address)




# Create BMS parser
bms_parser = JBDParser(database=args.db, db_table=args.dbtable, db_user=args.dbuser, db_pass=args.dbpass)


# Set BMS parser as the delegate for bluepy notifications. This how the raw BMS data gets passed into the parser
bt.setDelegate(bms_parser)



# Main loop
timer = 0
while True:

	if bt.waitForNotifications(0.5):
		continue

	if (time.time() - timer) > args.interval:
		timer = time.time()
		result = bt.writeCharacteristic(0x15, b'\xdd\xa5\x03\x00\xff\xfd\x77', True)	# write x03 (basic info)
		time.sleep(1) # Need time between writes?
		result = bt.writeCharacteristic(0x15, b'\xdd\xa5\x04\x00\xff\xfc\x77', True)	# write x04 (cell voltages)




