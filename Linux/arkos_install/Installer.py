#!/usr/bin/env python

########################################################################
##
##  arkOS Installer for Linux
##  Copyright (C) 2013 Jacob Cook
##  jacob@citizenweb.is
##
##  Uses elements of Raspbmc Installer, (C) 2013 Sam Nazarko
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software Foundation, either version 3 of the License, or
##  (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##  GNU General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see <http://www.gnu.org/licenses/>.
##
########################################################################

import json
import md5
import netifaces
import os
import re
import Queue
import socket
import ssl
import subprocess
import sys
import time
import urllib2
import xml.etree.ElementTree as ET

from PyQt4 import QtCore, QtGui


###################################################
##  Random Functions
###################################################

def error_handler(self, msg, close=True):
	# Throw up an error with the appropriate message and quit the application
	message = QtGui.QMessageBox.critical(self, 'Error', msg, 
		QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
	if close is True:
		os._exit(os.EX_CONFIG)

def success_handler(self, msg, close=False):
	# Throw up a success message
	message = QtGui.QMessageBox.information(self, 'Success', msg, 
		QtGui.QMessageBox.Ok, QtGui.QMessageBox.Ok)
	if close is True:
		os._exit(os.EX_CONFIG)

def centerOnScreen(window):
	resolution = QtGui.QDesktopWidget().screenGeometry()
	width = (resolution.width() / 2) - (window.frameSize().width() / 2)
	height = (resolution.height() / 2) - (window.frameSize().height() / 2)
	return width, height


###################################################
##  Welcome Dialog
################################################### 

class Assistant(QtGui.QWidget):
	def __init__(self):
		super(Assistant, self).__init__()

		# Create launcher window
		self.setFixedSize(375, 200)
		width, height = centerOnScreen(self)
		self.move(width, height)
		self.setWindowTitle('arkOS Installer')
		self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/icon.png')))

		btn1 = QtGui.QPushButton('Install arkOS to an SD card')
		btn1.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/install.png')))
		btn1.clicked.connect(self.installer)
		btn2 = QtGui.QPushButton('Search the network for arkOS devices')
		btn2.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/search.png')))
		btn2.clicked.connect(self.finder)

		vbox = QtGui.QVBoxLayout()
		banner = QtGui.QLabel()
		banner.setPixmap(QtGui.QPixmap(os.path.join(os.path.dirname(__file__), 'images/header.png')))
		banner.setAlignment(QtCore.Qt.AlignCenter)
		vbox.addWidget(banner)
		vbox.addWidget(btn1)
		vbox.addWidget(btn2)

		self.setLayout(vbox)
		self.check_priv()
		self.show()

	def check_priv(self):
		# Make sure the user has the privileges necessary to run
		if os.geteuid() != 0 and os.path.exists('/usr/bin/gksudo'):
			subprocess.Popen(["gksudo", "-D arkOS Installer", sys.executable, os.path.realpath(__file__)])
			os._exit(os.EX_CONFIG)
		elif os.geteuid() != 0 and os.path.exists('/usr/bin/kdesudo'):
			subprocess.Popen(["kdesudo", "--comment 'arkOS Installer'", sys.executable, os.path.realpath(__file__)])
			os._exit(os.EX_CONFIG)
		elif os.geteuid() != 0:
			error_handler(self, "You do not have sufficient privileges to run this program. Please run Installer.py, or 'sudo ./main.py' instead.")

	def installer(self):
		self.install = Installer()
		self.install.show()
		self.close()

	def finder(self):
		self.find = Finder()
		self.close()


###################################################
##  Network Browser
################################################### 

class AuthDialog(QtGui.QDialog):
	def __init__(self, parent, r, ip):
		super(AuthDialog, self).__init__(parent)
		self.setFixedSize(300, 150)
		width, height = centerOnScreen(self)
		self.move(width, height)
		self.setWindowTitle('Authenticate')
		self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/icon.png')))

		vbox = QtGui.QVBoxLayout()
		label = QtGui.QLabel("<b>Give the username/password of a qualified user on the device</b>")
		label.setWordWrap(True)
		table = QtGui.QGridLayout()
		ulabel = QtGui.QLabel('Username')
		uline = QtGui.QLineEdit()
		plabel = QtGui.QLabel('Password')
		pline = QtGui.QLineEdit()
		pline.setEchoMode(QtGui.QLineEdit.Password)
		table.addWidget(ulabel, 0, 0)
		table.addWidget(plabel, 1, 0)
		table.addWidget(uline, 0, 1)
		table.addWidget(pline, 1, 1)

		hbox = QtGui.QHBoxLayout()
		btn1 = QtGui.QPushButton('Cancel')
		btn1.clicked.connect(self.close)
		btn1.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/cancel.png')))
		btn2 = QtGui.QPushButton('OK')
		btn2.clicked.connect(lambda: self.send_sig(r, ip, uline, pline))
		btn2.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/ok.png')))
		btn2.setDefault(True)
		hbox.addStretch(1)
		hbox.addWidget(btn1)
		hbox.addWidget(btn2)

		vbox.addWidget(label)
		vbox.addLayout(table)
		vbox.addStretch(1)
		vbox.addLayout(hbox)

		self.setLayout(vbox)
		self.show()

	def send_sig(self, r, ip, user, passwd):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			sslSocket = ssl.wrap_socket(s, 
				ssl_version=ssl.PROTOCOL_TLSv1)
			sslSocket.settimeout(10.0)
			sslSocket.connect((ip, 8765))
			sslSocket.write(json.dumps({
				'request': r,
				'user': str(user.text()),
				'pass': str(passwd.text()),
				}))
			sent = True
			rsp = json.loads(sslSocket.read())
			if 'ok' in rsp['response']:
				success_handler(self, 'Signal to %s sent successfully.' % r)
				self.close()
			else:
				error_handler(self, 'Authentification failed', close=False)
			sslSocket.close()
		except Exception, e:
			if sent == True:
				success_handler(self, 'Signal to %s sent successfully, but I didn\'t get a response. '
					'Your command may or may not have completed.' % r)
				self.close()
			else:
				error_handler(self, 'There was an error processing your request.\n\n' + str(e), close=False)
			sslSocket.close()
 

class Finder(QtGui.QWidget):
	def __init__(self):
		super(Finder, self).__init__()

		# Create finder window
		self.setFixedSize(640, 400)
		width, height = centerOnScreen(self)
		self.move(width, height)
		self.setWindowTitle('arkOS Network Finder')
		self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/icon.png')))
		
		self.nodetype = None
		self.node = None

		vbox = QtGui.QVBoxLayout()
		self.tree_view = QtGui.QTreeWidget()
		self.tree_view.setHeaderLabels(['#', 'Name', 'IP Address', 'Genesis Status'])
		self.tree_view.setColumnWidth(0, 50)
		self.tree_view.setColumnWidth(1, 250)
		self.tree_view.setColumnWidth(2, 150)
		self.tree_view.setSortingEnabled(True)
		self.tree_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
		self.tree_view.header().setMovable(False)

		hbox = QtGui.QHBoxLayout()
		btn1 = QtGui.QPushButton('Scan')
		btn1.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/search.png')))
		btn1.clicked.connect(self.poll_nodes)
		hbox.addWidget(btn1)

		btn2 = QtGui.QPushButton('Shutdown')
		btn2.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/shutdown.png')))
		btn2.clicked.connect(lambda: self.sig_node('shutdown'))
		hbox.addWidget(btn2)

		btn3 = QtGui.QPushButton('Restart')
		btn3.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/restart.png')))
		btn3.clicked.connect(lambda: self.sig_node('restart'))
		hbox.addWidget(btn3)

		btn4 = QtGui.QPushButton('Reload Genesis')
		btn4.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/reload.png')))
		btn4.clicked.connect(lambda: self.sig_node('reload'))
		hbox.addWidget(btn4)

		vbox.addWidget(self.tree_view)
		vbox.addLayout(hbox)
		self.setLayout(vbox)

		self.show()

	def poll_nodes(self):
		self.tree_view.clear()
		QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
		num = 0
		nodes = []

		# Step 1: determine local network IP range
		# 	If there is only one IP address and netmask, we will use that
		#	If not, use the first class C network range that comes up
		ranges1 = []
		ranges = []
		ifaces = netifaces.interfaces()
		if 'lo' in ifaces:
			ifaces.remove('lo')
		for iface in ifaces:
			try:
				addr = netifaces.ifaddresses(iface)[netifaces.AF_INET]
			except KeyError:
				continue
			for item in addr:
				ranges1.append((item['addr'], item['netmask']))

		for item in ranges1:
			addr = item[0].split('.')
			mask = item[1].split('.')
			addr = '.'.join([str(int(addr[x]) & int(mask[x])) 
				for x in range(0,4)])
			binary_str = ''
			for octet in mask:
				binary_str += bin(int(octet))[2:].zfill(8)
			mask = str(len(binary_str.rstrip('0')))
			addrrange = addr + '/' + mask
			ranges.append(addrrange)

		for item in ranges:
			if item.startswith('127'):
				ranges.remove(item)

		if len(ranges) == 0:
			error_handler(self, 'I couldn\'t find any networks. Please make sure you are connected to a network.', close=False)
		elif len(ranges) == 1:
			addrrange = ''.join(ranges)
		else:
			for item in ranges:
				if item.startswith('192.168'):
					addrrange = item

		# Step 2: find all RPis on the network
		scan = subprocess.check_output(['nmap', '-oX', '-', '-sn', addrrange])
		hosts = ET.fromstring(scan)
		ips = []
		rpis = hosts.findall('.//address[@vendor="Raspberry Pi Foundation"]/..')
		for rpi in rpis:
			ips.append(rpi.find('.//address[@addrtype="ipv4"]').attrib['addr'])

		# Step 3: scan these RPis for Beacon instances
		for ip in ips:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			try:
				sslSocket = ssl.wrap_socket(s, 
					ssl_version=ssl.PROTOCOL_TLSv1)
				sslSocket.settimeout(10.0)
				sslSocket.connect((ip, 8765))
				sslSocket.write(json.dumps({
					'request': 'status'
					}))
				rsp = json.loads(sslSocket.read())
				if 'ok' in rsp['response']:
					nodes.append([num + 1, 
						rsp['name'], 
						ip, 
						rsp['status']
						])
				sslSocket.close()
			except:
				nodes.append([num + 1,
					'Unknown (Raspberry Pi)',
					ip,
					'Unknown'
					])
				sslSocket.close()

		# Step 4: format the list of RPis and statuses into the GUI list
		for node in nodes:
			nodelist = QtGui.QTreeWidgetItem(self.tree_view)
			for item in enumerate(node):
				nodelist.setText(item[0], str(item[1]))
		QtGui.QApplication.restoreOverrideCursor()

	def sig_node(self, r):
		try:
			node = self.tree_view.currentItem().text(2)
		except AttributeError:
			error_handler(self, 'Please make a selection', close=False)
			return

		if self.tree_view.currentItem().text(1).startsWith('Unknown'):
			error_handler(self, 'This feature can only be used on arkOS systems that have Beacon enabled', close=False)
			return

		authdlg = AuthDialog(self, r, node)


###################################################
##  Installer Wizard - Pages
###################################################  

class IntroPage(QtGui.QWizardPage):
	def __init__(self, parent=None):
		super(IntroPage, self).__init__(parent)
		
		# Introduction page
		self.setTitle('Introduction')
		label = QtGui.QLabel('Welcome to the arkOS Installer! This '
			'program will guide you through installing the arkOS image '
			'to an SD card inserted into your computer.\n\n'
			'Once you click Forward, your computer will start downloading '
			'the arkOS image from our servers in preparation for the '
			'install. Please make sure your computer is connected to the '
			'Internet before continuing.')
		label.setWordWrap(True)

		vbox = QtGui.QVBoxLayout()
		vbox.addWidget(label)

		self.setLayout(vbox)

	def nextId(self):
		return Installer.PageChooseMirror


class ChooseMirrorPage(QtGui.QWizardPage):
	def __init__(self, parent=None):
		super(ChooseMirrorPage, self).__init__(parent)
		self.parent = parent

		# Choose between the available mirrors
		self.setTitle('Choose Mirror')
		label = QtGui.QLabel('Choose the download mirror closest to your '
			'location.')
		label.setWordWrap(True)

		self.nybtn = QtGui.QRadioButton('New York (United States)')
		self.eubtn = QtGui.QRadioButton('Amsterdam (Europe)')
		self.eubtn.toggled.connect(self.set_selection)
		self.nybtn.setChecked(True)

		vbox = QtGui.QVBoxLayout()
		vbox.addWidget(label)
		vbox.addWidget(self.nybtn)
		vbox.addWidget(self.eubtn)

		self.setLayout(vbox)

	def nextId(self):
		return Installer.PageChooseDevice

	def set_selection(self):
		if self.nybtn.isChecked():
			self.parent.mirror = 'ny'
		else:
			self.parent.mirror = 'eu'


class ChooseDevicePage(QtGui.QWizardPage):
	def __init__(self, parent=None):
		super(ChooseDevicePage, self).__init__(parent)
		self.parent = parent

		# Select a device to write to
		self.setTitle('Choose Device')
		label = QtGui.QLabel('Choose the appropriate device from the '
			'list below. Devices smaller than the minimum (2 GB) are not shown. '
			'Note that it is very important to choose the correct device! '
			'If you choose another one you may seriously damage your system.')
		label.setWordWrap(True)

		self.tree_view = QtGui.QTreeWidget()
		self.tree_view.setHeaderLabels(['#', 'Device', 'Size', 'Unit'])
		self.tree_view.setColumnWidth(0, 50)
		self.tree_view.setColumnWidth(1, 375)
		self.tree_view.setColumnWidth(3, 50)
		self.tree_view.setSortingEnabled(True)
		self.tree_view.sortByColumn(0, QtCore.Qt.AscendingOrder)
		self.tree_view.header().setMovable(False)
		self.tree_view.itemSelectionChanged.connect(self.set_selection)

		btn1 = QtGui.QPushButton('Scan')
		btn1.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/search.png')))
		btn1.clicked.connect(self.poll_devices)

		vbox = QtGui.QVBoxLayout()
		vbox.addWidget(label)
		vbox.addWidget(btn1)
		vbox.addWidget(self.tree_view)

		self.setLayout(vbox)
		self.poll_devices()

	def set_selection(self):
		try:
			self.parent.device = self.tree_view.currentItem().text(1)
		except AttributeError:
			self.parent.device = ''
		self.emit(QtCore.SIGNAL('completeChanged()'))

	def poll_devices(self):
		# Pull up the list of connected disks
		self.tree_view.clear()
		self.parent.device = ''
		self.emit(QtCore.SIGNAL('completeChanged()'))
		QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
		devices = []
		num = 0
		fdisk = subprocess.Popen(['fdisk', '-l'], 
			stdout=subprocess.PIPE).stdout.readlines()
		mounts = subprocess.Popen(['mount'], 
			stdout=subprocess.PIPE).stdout.readlines()
		for lines in fdisk:
			if lines.startswith("/dev/") or lines.find("/dev/") == -1:
				continue

			dev = lines.split()[1].rstrip(":")
			r = re.compile("^\\s+([-,0-9. ]+)\\s+((?:[a-z][a-z]+))", re.IGNORECASE)
			m = r.match(lines.split(":")[1])
			size, unit = m.group(1), m.group(2)

			if unit == 'GB' and float(size) <= 2.0:
				continue
			elif unit == 'MB' and float(size) <= 2048.0:
				continue

			for thing in mounts:
				if dev in thing.split()[0] and thing.split()[2] == '/':
					break
			else:
				num = num + 1
				devices.append([num, dev, size, unit])

		for device in devices:
			devlist = QtGui.QTreeWidgetItem(self.tree_view)
			for item in enumerate(device):
				devlist.setText(item[0], str(item[1]))
		QtGui.QApplication.restoreOverrideCursor()

	def nextId(self):
		return Installer.PageAction

	def isComplete(self):
		if self.parent.device != '':
			return True
		else:
			return False


class ActionPage(QtGui.QWizardPage):
	def __init__(self, parent=None):
		super(ActionPage, self).__init__(parent)
		self.parent = parent

		# Confirm the mirror and device choices before dl/write
		# Then carry out the installation
		self.setTitle('Confirm Details')
		self.label = QtGui.QLabel('Please confirm the details below. Once you '
			'click Start, the download will begin, then the selected '
			'device will be erased and data will be overwritten.<br><br>'
			'<b>NOTE that there is no way to halt the writing process '
			'once it begins.</b><br>')
		self.label.setWordWrap(True)
		self.mirlabel = QtGui.QLabel()
		self.devlabel = QtGui.QLabel()

		self.btn = QtGui.QPushButton('Start Download/Install')
		self.btn.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/install.png')))
		self.btn.clicked.connect(self.install)

		self.vbox = QtGui.QVBoxLayout()
		self.vbox.addWidget(self.label)
		self.vbox.addWidget(self.mirlabel)
		self.vbox.addWidget(self.devlabel)
		self.vbox.addStretch(1)
		self.vbox.addWidget(self.btn)

		self.setLayout(self.vbox)

	def initializePage(self):
		if self.parent.mirror == 'eu':
			self.mirlabel.setText('<b>Mirror:</b> Amsterdam (European Union)')
		else:
			self.mirlabel.setText('<b>Mirror:</b> New York (United States)')
		self.devlabel.setText('<b>Device:</b> %s' % self.parent.device)

	def install(self):
		# Prepare the installation
		self.setTitle('Installing arkOS')
		if self.parent.mirror == 'eu':
			mirror_name = 'Amsterdam (European Union)'
		else:
			mirror_name = 'New York (United States)'

		self.label.close()
		self.mirlabel.close()
		self.devlabel.close()
		self.btn.close()
		self.dllabel = QtGui.QLabel("<b>Downloading image from " 
			+ mirror_name + "...</b>")
		self.imglabel = QtGui.QLabel()
		self.pblabel = QtGui.QLabel()
		self.progressbar = QtGui.QProgressBar()
		self.progressbar.setMinimum(0)
		self.progressbar.setMaximum(0)
		self.datalabel = QtGui.QLabel()
		self.vbox.addWidget(self.dllabel)
		self.vbox.addWidget(self.imglabel)
		self.vbox.addStretch(1)
		self.vbox.addWidget(self.progressbar)
		self.vbox.addWidget(self.datalabel)

		# Download package/MD5 if necessary
		override = self.pkg_check()
		if override == 0:
			# If no valid package was found, run the download and image writer threads
			self.download = Downloader(self.parent.queue, self.parent.mirror, 
				'latest.tar.gz.md5.txt')
			self.download.start()

			while self.download.isRunning():
				QtGui.QApplication.processEvents()
				time.sleep(0.1)

			download_result = self.parent.queue.get()
			if download_result != 200:
				error_handler(self, 'The file could not be downloaded. '
					'Please check your Internet connection. If the '
					'problem persists and your connection is fine, please '
					'contact the arkOS maintainers.\n\nHTTP Error ' 
					+ str(download_result))
				return

			self.progressbar.reset()
			self.progressbar.setMinimum(0)
			self.progressbar.setMaximum(100)

			self.download = Downloader(self.parent.queue, self.parent.mirror, 
				'latest.tar.gz')
			self.download.partDone.connect(self.updatebar)
			self.download.start()

			while self.download.isRunning():
				QtGui.QApplication.processEvents()
				time.sleep(0.1)

			download_result = self.parent.queue.get()
			if download_result != 200:
				error_handler(self, 'The file could not be downloaded. '
					'Please check your Internet connection. If the '
					'problem persists and your connection is fine, please '
					'contact the arkOS maintainers.\n\nHTTP Error ' 
					+ str(download_result))
				return

			self.dllabel.setText("Downloading image from " + mirror_name + 
				"... <b>DONE</b>")

			md5error = self.md5sum()
			if md5error == 0:
				error_handler(self, 'Installation failed: MD5 hashes are '
					'not the same. Restart the installer and it will '
					'redownload the package. If this error persists, please '
					'contact the arkOS maintainers.')
				return

		self.imglabel.setText("<b>Copying image to " + self.parent.device 
			+ "...</b><br>(This will take a few minutes depending on "
			"SD card size.)")
		self.progressbar.reset()
		self.progressbar.setMinimum(0)
		self.progressbar.setMaximum(0)

		self.write = ImgWriter(self.parent.queue, self.parent.device)
		self.datalabel.setText('Data write in progress.')
		self.write.start()

		while self.write.isRunning():
			QtGui.QApplication.processEvents()

		write_result = self.parent.queue.get()
		if write_result != False:
			error_handler(self, 'The disk writing process failed with the '
				'following error:\n\n' + write_result)
			return
		self.imglabel.setText('Copying image to ' + self.parent.device 
			+ '... <b>DONE</b>')
		self.parent.setPage(self.parent.PageConclusion, ConclusionPage(self.parent))
		self.parent.setOption(QtGui.QWizard.NoBackButtonOnLastPage, True)
		self.parent.next()

	def updatebar(self, val, got, total):
		self.progressbar.setValue(val)
		self.datalabel.setText("%0.1f of %0.1f MB" % (got, total))

	def pkg_check(self):
		# If package exists, check authenticity then skip download if necessary
		if os.path.exists('latest.tar.gz'):
			self.dllabel.setText('<b>Package found in working directory!</b> '
				'Checking authenticity...')
			while QtGui.QApplication.hasPendingEvents():
				QtGui.QApplication.processEvents()
			if os.path.exists('latest.tar.gz.md5.txt'):
				result = self.md5sum()
				if result == 0:
					# the md5s were different. continue with download as is
					self.dllabel.setText('Package found in working '
						'directory, but MD5 check failed. Redownloading...')
					return 0
				else:
					# the md5s were the same! skip the download.
					self.dllabel.setText('Authentic package found in '
						'working directory. Skipping download...')
					return 1
			else:
				if self.parent.mirror == 'eu':
					mirror_link = 'https://eupx.arkos.io/'
				else:
					mirror_link = 'https://uspx.arkos.io/'
				dl_md5 = urllib2.urlopen(mirror_link + 'latest.tar.gz.md5.txt')
				md5_File = open('latest.tar.gz.md5.txt', 'w')
				md5_File.write(dl_md5.read())
				md5_File.close()
				result = self.md5sum()
				if result == 0:
					# the md5s were different. gotta redownload the package
					self.dllabel.setText('Package found in working '
						'directory, but MD5 check failed. Redownloading...')
					return 0
				else:
					# the md5s were the same! skip the download.
					self.dllabel.setText('Authentic package found in '
						'working directory. Skipping download...')
					return 1
		return 0

	def md5sum(self):
		# Returns an md5 hash for the file parameter
		f = file('latest.tar.gz', 'rb')
		m = md5.new()
		while True:
			d = f.read(8096)
			if not d:
				break
			m.update(d)
		f.close()
		pack_md5 = m.hexdigest()
		file_md5 = open('latest.tar.gz.md5.txt')
		compare_md5 = file_md5.read().decode("utf-8")
		file_md5.close()
		if not pack_md5 in compare_md5:
			return 0
		else:
			return 1

	def isComplete(self):
		return False


class ConclusionPage(QtGui.QWizardPage):
	def __init__(self, parent=None):
		super(ConclusionPage, self).__init__(parent)
		self.parent = parent

		# Show success message and setup instructions
		self.setTitle('Installation Complete')
		label = QtGui.QLabel('Congratulations! Your image has been '
			'written to the SD card successfully.<br><br>Insert the SD card '
			'into your Raspberry Pi and connect it to your router.<br><br>'
			'After a minute or two, set up your server by opening your browser '
			'and connecting to Genesis at the following address:'
			'<br><b>http://arkOS:8000</b>'
			'<br>or use the Network Browser option in this Installer to '
			'find the IP address.<br><br>'
			'Your initial Genesis login credentials are:<br>'
			'Username: <b>admin</b><br>'
			'Password: <b>admin</b>')
		label.setWordWrap(True)
		self.box = QtGui.QCheckBox('Remove the downloaded files from your '
			'computer on exit')

		vbox = QtGui.QVBoxLayout()
		vbox.addWidget(label)
		vbox.addWidget(self.box)

		self.setLayout(vbox)

	def initializePage(self):
		self.parent.cancelbtn.close()

	def validatePage(self):
		if self.box.isChecked():
			os.unlink('latest.tar.gz')
			os.unlink('latest.tar.gz.md5.txt')
		return True


###################################################
##  Installer Wizard - Base Class
###################################################  

class Installer(QtGui.QWizard):
	NUM_PAGES = 5

	(PageIntro, PageChooseMirror, PageChooseDevice, PageAction, 
		PageConclusion) = range(NUM_PAGES)

	mirror = 'ny'
	device = ''
	queue = Queue.Queue()

	def __init__(self):
		super(Installer, self).__init__()

		# Create installer window
		self.setFixedSize(640, 400)
		width, height = centerOnScreen(self)
		self.move(width, height)
		self.setWindowTitle('arkOS Installer')
		self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), 'images/icon.png')))

		self.setPage(self.PageIntro, IntroPage(self))
		self.setPage(self.PageChooseMirror, ChooseMirrorPage(self))
		self.setPage(self.PageChooseDevice, ChooseDevicePage(self))
		self.setPage(self.PageAction, ActionPage(self))

		self.cancelbtn = QtGui.QPushButton('Cancel')
		self.cancelbtn.clicked.connect(self.quit_now)
		self.setButton(self.CustomButton1, self.cancelbtn)

		self.setOption(QtGui.QWizard.NoCancelButton, True)
		self.setOption(QtGui.QWizard.HaveCustomButton1, True)

		self.setStartId(self.PageIntro)

	def quit_now(self):
		# Run this when the user cancels or exits at a sensitive time
		msg = QtGui.QMessageBox.warning(self, 'Quit?', 
			'Are you sure you want to quit? The installation is not '
			'complete and you will not be able to use your SD card.\n\n'
			'If a disk write operation is in progress, this will not be '
			'able to stop that process.', QtGui.QMessageBox.Yes | 
			QtGui.QMessageBox.No, QtGui.QMessageBox.No)

		if msg == QtGui.QMessageBox.Yes:
			self.destroy()
			os._exit(os.EX_OK)
		else:
			return


###################################################
##  Installer Wizard - Threads for Long Processes
###################################################  

class Downloader(QtCore.QThread):
	"""

	Downloads the file passed to it.
	Args: queue - the message processing queue to pass HTTP errors
		  mirror - the ID of the chosen mirror
		  filename - the name of the file on the server to download

	"""

	partDone = QtCore.pyqtSignal((int, float, float))

	def __init__(self, queue, mirror, filename):
		super(Downloader, self).__init__()
		self.queue = queue
		if mirror == 'eu':
			self.mirror_link = 'https://eupx.arkos.io/'
		else:
			self.mirror_link = 'https://uspx.arkos.io/'
		self.filename = filename

	def run(self):
		# Download the files and report their status
		link = self.mirror_link + self.filename
		try:
			dl_file = urllib2.urlopen(link)
		except urllib2.HTTPError, e:
			self.queue.put(e.code)
			return
		io_file = open(self.filename, 'w')
		self.size_read(dl_file, io_file, 8192)
		io_file.close()
		self.queue.put(200)

	def size_read(self, response, file, chunk_size):
		# Continually compare the amount downloaded with what is left to get
		# Then pass that data back to the main thread to update the progressbar
		total_size = response.info().getheader('Content-Length').strip()
		total_size = int(total_size)
		bytes_so_far = 0
		while 1:
			chunk = response.read(chunk_size)
			file.write(chunk)
			bytes_so_far += len(chunk)
			if not chunk:
				break
			percent = (float(bytes_so_far) / total_size) * 100
			ptxt = float(bytes_so_far) / 1048576
			ptot = float(total_size) / 1048576
			self.partDone.emit(percent, ptxt, ptot)
		return bytes_so_far


class ImgWriter(QtCore.QThread):
	# Writes the downloaded image to disk
	def __init__(self, queue, device):
		super(ImgWriter, self).__init__()
		self.device = device
		self.queue = queue

	def run(self):
		# Write the image and refresh partition
		mounts = subprocess.Popen(['mount'], 
			stdout=subprocess.PIPE).stdout.readlines()
		for thing in mounts:
			if str(self.device) in thing.split()[0]:
				cmd = subprocess.Popen(['umount', str(thing).split()[0]]).wait()
		unzip = subprocess.Popen(['tar', 'xzOf', 'latest.tar.gz'], 
			stdout=subprocess.PIPE)
		dd = subprocess.Popen(
			['dd', 'status=noxfer', 'bs=1M', 'of=' + self.device], 
			stdin=unzip.stdout, stderr=subprocess.PIPE)
		error = dd.communicate()[1]
		if "error" in error:
			self.queue.put(error)
		else:
			self.queue.put(False)
			subprocess.Popen(['blockdev', '--rereadpt', self.device])


def main():
	app = QtGui.QApplication(sys.argv)
	asst = Assistant()
	sys.exit(app.exec_())

if __name__ == '__main__':
	main()
