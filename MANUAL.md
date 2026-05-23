# audiograbd setup manual



## Clone the repo and install dependencies

Clone this repository:
```
git clone https://codeberg.org/ove/audiograbd.git
```

To the repository:
```
cd audiograbd
```

Install ``uv``:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Sync dependencies:
```
uv sync
```

Install packages:
```
sudo apt install screen ffmpeg pkexec -y
```


## Configure EEPROM
Open the EEPROM configuration:
```
sudo -E rpi-eeprom-config --edit
```
Disable power off on halt, keeping the PMIC on when the Compute Module is halted:
```
POWER_OFF_ON_HALT=0
```
The Audiograb System was built around having the PMIC supply peripherals with 3.3V. If you are testing or adapting to a different system, you can leave it as it is.


## User Configuration

### Setting up ``polkit`` rules

Add the following lines to `/etc/polkit-1/rules.d/mount.rules`, replacing `user` with your username:
```
polkit.addRule(function(action, subject) {
	if ((
		action.id == "org.freedesktop.udisks2.filesystem-mount" ||
		action.id == "org.freedesktop.udisks2.filesystem-unmount" ||
		action.id == "org.freedesktop.udisks2.filesystem-mount-other-seat" ||
		action.id == "org.freedesktop.udisks2.power-off-drive-other-seat" ||
		action.id == "org.freedesktop.udisks2.eject-media"
		) && subject.user == "user"
	)
	{
		return polkit.Result.YES;
	}
});
```

Add the following lines to `/etc/polkit-1/rules.d/login.rules`:
```
polkit.addRule(function(action, subject) {
	if ((
		action.id == "org.freedesktop.login1.reboot" ||
		action.id == "org.freedesktop.login1.reboot-multiple-sessions" ||
		action.id == "org.freedesktop.login1.power-off" ||
		action.id == "org.freedesktop.login1.halt" ||
		action.id == "org.freedesktop.login1.power-off-multiple-sessions"
		) && subject.user == "user"
	)
	{
		return polkit.Result.YES;
	}
});
```

Add the following lines to `/etc/polkit-1/rules.d/wakealarm.rules`:
```
polkit.addRule(function(action, subject) {
    if (action.id === "org.audiograbd.wakealarm" &&
        subject.user === "user") {
        return polkit.Result.YES;
    }
});
```

Add the following lines to `/usr/share/polkit-1/actions/org.audiograbd.wakealarm.policy`:
```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
  "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.audiograbd.wakealarm">
    <description>Set RTC wake alarm</description>
    <message>Set RTC wake alarm</message>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/local/bin/wakealarm.sh</annotate>
    <annotate key="org.freedesktop.policykit.exec.allow_gui">false</annotate>
    <defaults>
      <allow_any>no</allow_any>
      <allow_inactive>no</allow_inactive>
      <allow_active>no</allow_active>
    </defaults>
  </action>
</policyconfig>
```


## Install ``wakealarm.sh``

Change ownership:
```
chown root:root wakealarm.sh
```
Set permissions:
```
sudo chmod 755 wakealarm.sh
```
Install:
```
sudo cp wakealarm.sh /usr/local/bin/wakealarm.sh
```



## Select Storage Provider

Select a storage provider, or implement your own with the ``StorageProvider`` class. The following providers are already included.


### Sigma2

Apply for resources at: [https://www.sigma2.no/apply-e-infrastructure-resources](https://www.sigma2.no/apply-e-infrastructure-resources)


### Google Cloud Storage
See [https://cloud.google.com/storage](https://cloud.google.com/storage).
Set an environment variable with the path to your credentials:
```
export GOOGLE_APPLICATION_CREDENTIALS="key.json"
```


## QMI modem setup
Follow the documentation at: [https://wiki.seeedstudio.com/raspberry_pi_4g_lte_hat_qmi/](https://wiki.seeedstudio.com/raspberry_pi_4g_lte_hat_qmi/)

Check if the ``qmi_wwan`` kernel module is loaded:
```
lsmod | grep qmi_wwan
```
If not, add the following to ``/etc/modules-load.d/qmi_wwan.conf``:
```
qmi_wwan
```
Reboot, and check again. You should see something like this:
```
qmi_wwan               65536  0
cdc_wdm                49152  1 qmi_wwan
```
Check if the USB interface is exposed:
```
lsusb | grep Quectel
```
You should get something like this:
```
Bus 004 Device 004: ID 2c7c:0801 Quectel Wireless Solutions Co., Ltd. RM520N-GL
```
Check diagnostic messages:
```
dmesg | grep -i ttyUSB
```
You should see that the modem is attached to the following devices:
```
[625.808526] usb 4-1: GSM modem (1-port) converter now attached to ttyUSB0
[625.808643] usb 4-1: GSM modem (1-port) converter now attached to ttyUSB1
[625.808758] usb 4-1: GSM modem (1-port) converter now attached to ttyUSB2
[625.811255] usb 4-1: GSM modem (1-port) converter now attached to ttyUSB3
```
One of these is the primary AT command port, which can be found experimentally. In my case, it was ``ttyUSB2``. Connect the SIM card, and use ``screen`` to communicate with the modem:
```
screen /dev/ttyUSB2 115200
```
Type the following:
```
AT+CPIN?
```
You should see:
```
+CPIN: SIM PIN

OK
```

Type the following, replacing the empty string with your SIM card PIN code:
```
AT+CPIN=""
```

You should see:
```
OK

+CPIN: READY

+QUSIM: 1

+QIND: SMS DONE

+QIND: PB DONE
```
Check if the modem interface is up and running:
```
ifconfig | grep wwan0
```
You should see:
```
wwan0: flags=4305<UP,POINTOPOINT,RUNNING,NOARP,MULTICAST>  mtu 1500
```
Check connectivity by pinging through the modem interface:
```
ping -c 3 -I wwan0 ntnu.no
```













## Running as a systemd service
If running as a systemd service, make sure it has access to D-Bus:
```
[Service]
User=user
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
```