#include <libusb-1.0/libusb.h>
#include <libudev.h>

// C library headers
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <math.h>
#include <pthread.h>
#include <signal.h> 
#include <time.h>
#include <inttypes.h>
#include <unistd.h>

// sys headers
#include <sys/msg.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/ioctl.h>

// linux headers
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <linux/spi/spidev.h>

// Linux headers
#include <fcntl.h>   // Contains file controls like O_RDWR
#include <errno.h>   // Error integer and strerror() function
#include <termios.h> // Contains POSIX terminal control definitions

// other headers
#include <netinet/in.h>
#include "dac8164.h"
#include "MCP23S08.h"
#include "gpio.h"
#include "utils.h"
#include <i2c/smbus.h>
#include "i2cbusses.h"


// ----- libusb constants and variables ----- //
#define HISTORY_LENGTH 100
#define VENDOR_ID_0 0xcaf0
#define VENDOR_ID_1 0xcaf1
#define PRODUCT_ID 0x4003


struct libusb_device_handle *device_handle_0 = NULL;
struct libusb_device_handle *device_handle_1 = NULL;

pthread_t acquisition_thread_0;
pthread_t command_execution_thread;


// socket constant
#define PORT 12000

DAC8164 dac[3]; // HV DAQ objects

// variables to store LV i2c connection info
int lv_i2cbus;
static int lv_i2c = 0;

// thread locking vars
pthread_mutex_t lock;
pthread_mutex_t usb0_mutex_lock;
pthread_mutex_t usb1_mutex_lock;

// assorted values to be returned upon client request
float voltages_0[6];
float voltages_1[6];

float currents_0[6];
float currents_1[6];




// LV channel information
uint8_t powerChMap[6] = {5, 6, 7, 2, 3, 4};
uint8_t lv_mcp_reset = 3;
uint8_t lv_global_enable = 18;

// get time that server started
int start_time;

int current_datafile_time = 0;
int current_num_storages = 0;
int current_max_storages = 1250000;
float last_current_output[6];

#define full_current_history_length 8000

typedef struct
{
  float all_currents[6][HISTORY_LENGTH];
  float all_currents_stored[6][HISTORY_LENGTH];
  uint8_t array_indicator;
  uint8_t pico;
  uint8_t join_thread;
} arg_struct;

// ----- Structures used in server communications with clients ----- //


typedef struct {
  int client_addr;
} client_data ;

uint8_t spi_bpw = 8; // bits per word
uint32_t spi_speed = 40000000; // 10MHz
uint16_t spi_delay = 0;

int spiFds;

static const uint8_t spi_mode = 0;

static const char* spidev = "/dev/spidev0.0"; //this is the SPI device. Assume here that there is only one SPI bus

MCP* hvMCP;
MCP* lvpowerMCP;
MCP* lvpgoodMCP;

#define SPISPEED 40000000
#define NSTEPS 200
#define SPICS 0

const char *LIVE_STATUS_FILENAME = "../live_status.txt";
char pipe_path_base[14] = "/tmp/data_pipe";
char v_pipe_path_base[15] = "/tmp/vdata_pipe";

#define ALPHA 0.1 // Choose a value between 0 and 1. Smaller values result in heavier filtering.
#define DECIMATION_FACTOR 10
uint8_t use_pipe = 1; // when server tries to open pipe, will be set to 0 upon fail - will then assume pipe is not to be used

int num_pipes = 3;
int pipe_channels[3] = {0, 1, 3};


// variables to manage command queue
command incoming_commands[COMMAND_LENGTH];
int command_array[COMMAND_LENGTH];
int Rear = 0;
int Front = 0;

command add_command;

// initialize queue variables
int queue_key;
int queue_id;
int msqid;

int pico_queue_key;
int pico_queue_id;
int pico_msqid;





command parse_queue() {
  command return_command;

  long msgtyp = 0;

  msgrcv(msqid, (void *)&return_command, 56, msgtyp, MSG_NOERROR | IPC_NOWAIT);

  return return_command;
}

command parse_pico_queue() {
  command return_command;

  long msgtyp = 0;

  msgrcv(pico_msqid, (void *)&return_command, 56, msgtyp, MSG_NOERROR | IPC_NOWAIT);

  return return_command;
}

float i2c_ltc2497(int address, int channelLTC)
{
  float max_reading = 8388608.0;
  float vref = 1.24;

  unsigned char block[I2C_SMBUS_BLOCK_MAX];

  set_slave_addr(lv_i2c, address, 1);

  //----- WRITE BYTES -----
  block[0] = channelLTC;
  int length = 1;                             //<<< Number of bytes to write
  if (write(lv_i2c, block, length) != length) // write() returns the number of bytes actually written, if it doesn't match then an error occurred (e.g. no response from the device)
  {
    /* ERROR HANDLING: i2c transaction failed */
    perror("Failed to write to the i2c bus.");
    return -1;
  }

  msleep(500);

  //----- READ BYTES -----
  length = 3;                                //<<< Number of bytes to read
  if (read(lv_i2c, block, length) != length) // read() returns the number of bytes actually read, if it doesn't match then an error occurred (e.g. no response from the device)
  {
    // ERROR HANDLING: i2c transaction failed
    perror("Failed to read from the i2c bus.");
    return -1;
  }

  uint32_t val = ((block[0] & 0x3f) << 16) + (block[1] << 8) + (block[2] & 0xE0);

  return val * vref / max_reading;
}



int powerOn(uint8_t channel, int client_addr) {
  char* command_log = load_config("Command_Log_File");

  if (write_gpio_value(lv_global_enable, HIGH) == -1) {
    perror("poweron error 0");
    return -1;
  }
  
  if (channel == 6) {
    for (int i=0; i<6; i++) {
      if (MCP_pinWrite(lvpgoodMCP, powerChMap[i], HIGH) == -1) {
        perror("poweron error 1");
        return -1;
      }


      // log powerOn command
      char log_message[12];
      snprintf(log_message, 12, "powerOn: %i", i);
      write_log(command_log, log_message, 1, client_addr);
    }
  } else {
    if (MCP_pinWrite(lvpgoodMCP, powerChMap[channel], HIGH) == -1) {
      perror("poweron error 2");
      return -1;
    }

    // log powerOn command
    char log_message[12];
    snprintf(log_message, 12, "powerOn: %i", channel);
    write_log(command_log, log_message, 1, client_addr);
  }

  return 0;
}

int powerOff(uint8_t channel, int client_addr) {
  char *command_log = load_config("Command_Log_File");

  if (channel == 6) {
    if (write_gpio_value(lv_global_enable, LOW) == -1) {
      perror("poweroff error 0");
      return -1;
    }
    
    for (int i=0; i<6; i++) {
      if (MCP_pinWrite(lvpgoodMCP, powerChMap[i], LOW) == -1) {
        perror("poweroff error 1");
        return -1;
      }

      // log powerOff command
      char log_message[13];
      snprintf(log_message, 12, "powerOff: %i", i);
      write_log(command_log, log_message, 1, client_addr);
    }
  } else {
    if (MCP_pinWrite(lvpgoodMCP, powerChMap[channel], LOW) == -1) {
      perror("poweroff error 2");
      return -1;
    }

    // log powerOff command
    char log_message[13];
    snprintf(log_message, 12, "powerOff: %i", channel);
    write_log(command_log, log_message, 1, client_addr);
  }

  return 0;
}

int hv_initialization(){
  if (MCP_pinMode(hvMCP, 4, OUTPUT) == -1) {
    return -1;
  } else if (MCP_pinMode(hvMCP, 4, LOW) == -1) {
    return -1;
  } else if (MCP_pinMode(hvMCP, 2, OUTPUT) == -1) {
    return -1;
  } else if (MCP_pinWrite(hvMCP, 2, LOW) == -1) {
    return -1;
  } else if (DAC8164_setup (&dac[0], hvMCP, 6, 7, 0, -1, -1) == -1) {
    return -1;
  } else if (DAC8164_setup (&dac[1], hvMCP, 3, 7, 0, -1, -1) == -1) {
    return -1;
  } else if (DAC8164_setup (&dac[2], hvMCP, 5, 7, 0, -1, -1) == -1) {
    return -1;
  }

  return 0;
}

void set_hv(int channel, float value)
{
  int idac = (int)(channel / 4);
  float alphas[12] = {0.9, 0.9, 0.885, 0.9, 0.9012, 0.9034, 0.9009, 0.9027, 0.8977, 0.9012, 0.9015, 1.};

  uint32_t digvalue = ((int)(alphas[channel] * 16383. * (value / 1631.3))) & 0x3FFF;

  DAC8164_writeChannel(&dac[idac], channel, digvalue);
}



// get_vhv
void get_vhv(uint8_t channel, int client_addr) {
  float return_val;

  if (channel < 6) {
    return_val = voltages_0[channel];
  } else {
    return_val = voltages_1[channel - 6];
  }

  int float_channel = (int)channel;

  write(client_addr, &return_val, sizeof(return_val));


}

// get_ihv
void get_ihv(uint8_t channel, int client_addr)
{
  float return_val;
  if (channel < 6) {
    return_val = currents_0[channel];
  } else {
    return_val = currents_1[channel - 6];
  }

  write(client_addr, &return_val, sizeof(return_val));
}

// get_buffer_status
void get_buffer_status(uint8_t channel, int client_addr) {
  uint8_t send_val = 95;

  printf("In get buffer status\n");

  char *input_data;
  input_data = (char *)malloc(1);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_0, 0x82, input_data, sizeof(input_data), 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_1, 0x82, input_data, sizeof(input_data), 0, 0);
  }

  int return_val = 1;

  if ((*input_data & 1 << (channel)) == 0) {
    return_val = 0;
  }
 

}

void get_slow_read(uint8_t channel, int client_addr) {
  uint8_t send_val = 97;

  char *input_data;
  input_data = (char *)malloc(1);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_0, 0x82, input_data, sizeof(input_data), 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_1, 0x82, input_data, sizeof(input_data), 0, 0);
  }

  

  int return_val = (int) *input_data;
  printf("slow read value of: %i\n", return_val);

  write(client_addr, &return_val, sizeof(return_val));
}


// returns 10 value from full speed current buffer
void current_burst(uint8_t channel, int client_addr) {
  struct libusb_device_handle *device_handle;


  if (channel < 6) {
    device_handle = device_handle_0;
  } else {
    device_handle = device_handle_1;
  }

  uint8_t get_buffer = 89 + channel;
  
  char *current_input_data;
  current_input_data = (char *)malloc(64);

  float current_array[16];

  libusb_bulk_transfer(device_handle, 0x02, &get_buffer, 1, 0, 50);

  int return_val = libusb_bulk_transfer(device_handle, 0x82, current_input_data, 64, 0, 500);

  for (int i=0; i<10; i++) {
    current_array[i] = *(float *)&current_input_data[4*i];
  }

  write(client_addr, &current_array, sizeof(current_array));
}

void start_buffer(uint8_t channel, int client_addr) {
  uint8_t start_buffer = 87;

  struct libusb_device_handle *device_handle;

  if (channel < 6) {
    device_handle = device_handle_0;
  } else {
    device_handle = device_handle_1;
  }

  libusb_bulk_transfer(device_handle, 0x02, &start_buffer, 1, 0, 0);
}


void stop_buffer(uint8_t channel, int client_addr) {
  uint8_t stop_buffer = 88;

  struct libusb_device_handle *device_handle;

  if (channel < 6) {
    device_handle = device_handle_0;
  } else {
    device_handle = device_handle_1;
  }

  libusb_bulk_transfer(device_handle, 0x02, &stop_buffer, 1, 0, 0);
}


// rampHV
void ramp_hv(uint8_t channel, float voltage, int client_addr) {
  char *command_log = load_config("Command_Log_File");

  int idac = (int)(channel / 4);
  float increment = voltage / NSTEPS;
  float current_value = 0;

  for (int itick=0; itick<NSTEPS; itick++) {
    usleep(50000);
    current_value += increment;

    set_hv(channel, current_value);
  }

  // log ramp_hv command
  char log_message[12];
  snprintf(log_message, 12, "ramp_hv: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}


void down_hv(uint8_t channel, int client_addr) {
  
  char *command_log = load_config("Command_Log_File");

  float current_voltage;
  if (channel < 6) {
    current_voltage = voltages_0[channel];
  } else {
    current_voltage = voltages_1[channel - 6];
  }

  int idac = (int)(channel / 4);
  float increment = current_voltage / NSTEPS;

  for (int itick = 0; itick < NSTEPS; itick++) {
    usleep(50000);
    current_voltage -= increment;
    set_hv(channel, current_voltage);
  }

  set_hv(channel,0);

  // log down_hv command
  char log_message[12];
  snprintf(log_message, 12, "down_hv: %u", channel);
  write_log(command_log, log_message, 0, client_addr);

}

// trip
void trip(uint8_t channel, int client_addr)
{
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val = 103 + (channel % 6);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log trip command
  char log_message[12];
  snprintf(log_message, 12, "tripped: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// reset_trip
void reset_trip(uint8_t channel, int client_addr)
{
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val = 109 + (channel % 6);


  if (channel < 6) {
    printf("reset trip channel %u\n",channel);
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    printf("reset all trips\n");
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log reset_trip command
  char log_message[15];
  snprintf(log_message, 15, "reset_trip: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// disable_trip
void disable_trip(uint8_t channel, int client_addr)
{
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val = 115 + (channel % 6);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log disable_trip command
  char log_message[17];
  snprintf(log_message, 17, "disable_trip: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// enable_trip
void enable_trip(uint8_t channel, int client_addr)
{
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val = 121 + (channel % 6);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log enable_trip command
  char log_message[16];
  snprintf(log_message, 16, "enable_trip: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// enable_ped
void enable_ped(uint8_t channel, int client_addr)
{

  printf("in enable ped\n");
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val = 37;

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log enable_ped command
  char log_message[15];
  snprintf(log_message, 15, "enable_ped: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// disable_ped
void disable_ped(uint8_t channel, int client_addr)
{
  printf("in disable_ped\n");

  char *command_log = load_config("Command_Log_File");
  
  uint8_t send_val = 38;

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
  }

  // log disable_ped command
  char log_message[16];
  snprintf(log_message, 16, "disable_ped: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}


// trip_status
void trip_status(uint8_t channel, int client_addr)
{
  uint8_t send_val = 33;

  char *input_data;
  input_data = (char *)malloc(1);

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_0, 0x82, input_data, sizeof(input_data), 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val, 1, 0, 0);
    libusb_bulk_transfer(device_handle_1, 0x82, input_data, sizeof(input_data), 0, 0);
  }

  int return_val = 1;

  if ((*input_data & 1 << (channel)) == 0) {
    return_val = 0;
  }

  if (client_addr != -9999) {
    write(client_addr, &return_val, sizeof(return_val));
  } else {
    write_fixed_location(LIVE_STATUS_FILENAME, 2 * channel, return_val); // writes at fixed location
  }
}

// set_trip
void set_trip(uint8_t channel, float value, int client_addr)
{
  char *command_log = load_config("Command_Log_File");

  uint8_t send_val[3];
  send_val[0] = 76 + (channel % 6);

  uint16_t send_int;
  send_int = (uint16_t)(value / 1000 * 65535);

  uint8_t right_mask = -1;

  send_val[1] = send_int >> 8 & right_mask;
  send_val[2] = send_int & right_mask;

  uint16_t one = send_val[1] << 8;
  uint16_t two = send_val[2] + one;

  if (channel < 6) {
    libusb_bulk_transfer(device_handle_0, 0x02, &send_val[0], sizeof(send_val), 0, 0);
  } else {
    libusb_bulk_transfer(device_handle_1, 0x02, &send_val[0], sizeof(send_val), 0, 0);
  }

  // log set_trip command
  char log_message[13];
  snprintf(log_message, 13, "set_trip: %u", channel);
  write_log(command_log, log_message, 0, client_addr);
}

// readMonV48
void readMonV48(uint8_t channel, int client_addr)
{
  uint8_t LTCaddress[6] = {0x26, 0x26, 0x16, 0x16, 0x14, 0x14};
  uint8_t v48map[6] = {6, 0, 6, 0, 6, 0};

  float v48scale = 0.0012089;
  float acplscale = 8.2;

  uint8_t index = v48map[channel];
  uint8_t channelLTC = (5 << 5) + index;
  uint8_t address = LTCaddress[channel];

  float ret = i2c_ltc2497(address, channelLTC);
  ret = ret / (v48scale * acplscale);

  write(client_addr, &ret, sizeof(ret));
}

// readMonI48
void readMonI48(uint8_t channel, int client_addr)
{
  uint8_t LTCaddress[6] = {0x26, 0x26, 0x16, 0x16, 0x14, 0x14};
  uint8_t i48map[6] = {7, 1, 7, 1, 7, 1};

  float i48scale = 0.010;
  float acplscale = 8.2;

  uint8_t index = i48map[channel];
  uint8_t channelLTC = (5 << 5) + index;
  uint8_t address = LTCaddress[channel];

  float ret = i2c_ltc2497(address, channelLTC);
  ret = ret / (i48scale * acplscale);

  write(client_addr, &ret, sizeof(ret));
}

// readMonV6
void readMonV6(uint8_t channel, int client_addr)
{
  uint8_t v6map[6] = {4, 3, 4, 3, 4, 3};
  uint8_t LTCaddress[6] = {0x26, 0x26, 0x16, 0x16, 0x14, 0x14};

  float v6scale = 0.00857905;
  float acplscale = 8.2;

  uint8_t index = v6map[channel];
  uint8_t channelLTC = (5 << 5) + index;
  uint8_t address = LTCaddress[channel];

  float ret = i2c_ltc2497(address, channelLTC);
  ret = ret / (v6scale * acplscale);

  write(client_addr, &ret, sizeof(ret));
}

// readMonI6
void readMonI6(uint8_t channel, int client_addr)
{
  uint8_t addresses[3] = {0x14, 0x16, 0x26};
  uint8_t LTCaddress[6] = {0x26, 0x26, 0x16, 0x16, 0x14, 0x14};
  uint8_t i6map[6] = {5, 2, 5, 2, 5, 2};

  float i6scale = 0.010;
  float acplscale = 8.2;

  uint8_t index = i6map[channel];
  uint8_t channelLTC = (5 << 5) + index;
  uint8_t address = LTCaddress[channel];

  float ret = i2c_ltc2497(address, channelLTC);
  ret = ret / (i6scale * acplscale);

  write(client_addr, &ret, sizeof(ret));
}

void *command_execution() {
  while (1) {
    
    
    command check_command = parse_queue();
    

    char current_command = check_command.command_name;
    char current_type = check_command.command_type;
    uint8_t char_parameter = (uint8_t)check_command.char_parameter-97;
    float float_parameter = check_command.float_parameter;
    int client_addr = check_command.client_addr;


    // check if command is hv type, else do nothing
    if (current_type == 'a')
    {
      // select proper hv function
      if (current_command == 'a') { // get_vhv
        get_vhv(char_parameter, client_addr);
      } else if (current_command == 'b') { // get_ihv
        get_ihv(char_parameter, client_addr);
      } else if (current_command == '(') {
        msleep(20);
        current_burst(char_parameter, client_addr);
      } else if (current_command == ')') {
        start_buffer(char_parameter, client_addr);
      } else if (current_command == '*') {
        stop_buffer(char_parameter, client_addr);
      } else if (current_command == '+') {
        get_buffer_status(char_parameter, client_addr);
      } else if (current_command == 'y') {
        get_slow_read(char_parameter, client_addr);
      }
    }

    if (current_type == 'a') {
      // select proper hv function
      if (current_command == 'c') { // ramp_hv
        ramp_hv(char_parameter, float_parameter, client_addr);

      } else if (current_command == 'd') { // down_hv
        down_hv(char_parameter, client_addr);
      }
    }


    if (current_type == 'b')
    {

      // select proper lv function
      if (current_command == 'g') { // readMonV48
        readMonV48(char_parameter, client_addr);
      } else if (current_command == 'h') { // readMonI48
        readMonI48(char_parameter, client_addr);
      } else if (current_command == 'i') { // readMonV6
        readMonV6(char_parameter, client_addr);
      } else if (current_command == 'j') { // readMonI6
        readMonI6(char_parameter, client_addr);
      } else if (current_command == 'e') { // powerOn
        int errval = powerOn(char_parameter, client_addr);

        if (errval == -1) {
          error_log("LV powerOn Error");
        }

      } else if (current_command == 'f') { // powerOff
        powerOff(char_parameter, client_addr);
      }
    }
    sleep(0.1);
  }
}




// ----- Code to handle socket stuff ----- //
void *handle_client(void *args) {
  client_data *client_information = args;

  int inner_socket = client_information->client_addr;

  char buffer[9];
  char flush_buffer[1];


  while (1)
  {
    int return_val = read(inner_socket, buffer, 9);

    // if return_val is -1, terminate thread
    if (return_val == 0) {

      printf("Thread terminated \n");
      return 0;
    }

    if (return_val == 9)
    {
      // create command
      add_command.command_name = buffer[0];
      add_command.command_type = buffer[1];
      add_command.char_parameter = buffer[2];
      add_command.float_parameter = atof(&buffer[3]);
      add_command.client_addr = inner_socket;

      // add command to linux kernel queue
      if (add_command.command_type == 'c') {
        msgsnd(pico_msqid, (void *)&add_command, sizeof(add_command), IPC_NOWAIT);
      } else {
        msgsnd(msqid, (void *)&add_command, sizeof(add_command), IPC_NOWAIT);
      }

    }
  }
}

// ----- Code to handle socket stuff ----- //
void *live_status(void *args) {
  char buffer[9];
  char flush_buffer[1];

  while (1) {

    for (int ichannel = 0; ichannel < 6; ichannel++) {
      // create command
      add_command.command_name = 'o';
      add_command.command_type = 'c';
      add_command.char_parameter = ichannel + 97;
      add_command.float_parameter = 0;
      add_command.client_addr = -9999;

      // add command to queue
      msgsnd(pico_msqid, (void *)&add_command, sizeof(add_command), IPC_NOWAIT);

    }
    sleep(2);
  }
}

void *create_connections()
{

  int server_fd, new_socket, valread;
  struct sockaddr_in address;
  int opt = 1;
  int addrlen = sizeof(address);

  // Creating socket file descriptor
  if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
    perror("socket failed");
    exit(EXIT_FAILURE);
  }

  // Forcefully attaching socket to the port 8080
  if (setsockopt(server_fd, SOL_SOCKET,
                 SO_REUSEADDR | SO_REUSEPORT, &opt,
                 sizeof(opt)))
  {
    perror("setsockopt");
    exit(EXIT_FAILURE);
  }
  address.sin_family = AF_INET;
  address.sin_addr.s_addr = INADDR_ANY;
  address.sin_port = htons(PORT);

  // Forcefully attaching socket to the port 8080
  if (bind(server_fd, (struct sockaddr *)&address,
           sizeof(address)) < 0)
  {
    perror("bind failed");
    exit(EXIT_FAILURE);
  }
  if (listen(server_fd, 3) < 0)
  {
    perror("listen");
    exit(EXIT_FAILURE);
  }

  while (1)
  {
    if ((new_socket = accept(server_fd, (struct sockaddr *)&address,
                             (socklen_t *)&addrlen)) < 0)
    {
      perror("accept");
      exit(EXIT_FAILURE);
    }

    pthread_t client_thread;
    pthread_create(&client_thread, NULL, handle_client, &new_socket);
  }
}




int write_voltages(char *filename_V, float voltages[6]) {
  FILE *fp_V = fopen(filename_V, "a");
  if (fp_V == NULL) {
    printf("Error opening the voltage file %s", filename_V);
  }
  time_t seconds;

  char buffer[1024]; // A buffer to format and write data
  for (int channel = 0; channel < 6; channel++) {
    fprintf(fp_V, "%f ", voltages_0[channel]);
  }

  seconds = time(NULL);
  fprintf(fp_V, "%f\n", (float)seconds);
  fclose(fp_V);
}



int write_pipe_currents(int fd[num_pipes], float store_all_currents_internal[6][HISTORY_LENGTH]) {
      char buffer[1024];

      for (int pipe_id=0; pipe_id<num_pipes; pipe_id++) {
        for (uint32_t time_index = 0; time_index < HISTORY_LENGTH; time_index++)
        {
    
          for (uint8_t channel = 0; channel < 6; channel++)
          {
            // Apply the first-order low-pass filter
            float input_value = store_all_currents_internal[channel][time_index];
            float filtered_value = ALPHA * input_value + (1 - ALPHA) * last_current_output[channel];
            last_current_output[channel] = filtered_value;

            // Decimation by 5: Only write every 5th sample
            if (time_index % DECIMATION_FACTOR == 0 && use_pipe == 1)
            {
              int length = snprintf(buffer, sizeof(buffer), "%f ", filtered_value);

              write(fd[pipe_id], buffer, length); // Write to the pipe
            }
          }

          if (time_index % DECIMATION_FACTOR == 0 && use_pipe == 1)
          {
            int length = snprintf(buffer, sizeof(buffer), "\n");
            write(fd[pipe_id], buffer, length); // Write the timestamp to the pipe
          }
        }
        
      }
      return 0;
}


int write_pipe_voltages(int pico, int vfd[6], float voltages_0[6]) {
    if (pico == 0)
    {
      char buffer[1024]; // A buffer to format and write data
      for (int channel = 0; channel < 6; channel++)
      {
        // only write to pipe if connection was properly established earlier
        for (int pipe_id=0; pipe_id<num_pipes; pipe_id++) {
          if (use_pipe == 1) {
            int length = snprintf(buffer, sizeof(buffer), "%f ", voltages_0[channel]);
            write(vfd[pipe_id], buffer, length); // Write to the pipe
          }
        }

      }
    }
    int seconds = time(NULL);

    if (pico == 0 && use_pipe == 1) {
      char buffer[1024]; // A buffer to format and write data
      int length = snprintf(buffer, sizeof(buffer), "\n");
      for (int pipe_id=0; pipe_id<num_pipes; pipe_id++) {
        write(vfd[pipe_id], buffer, length); // Write to the pipe
      }
    }

    return 0;
}




int initialize_libusb(int pico) {


  // Set debugging output to max level
	libusb_set_option( NULL, LIBUSB_OPTION_LOG_LEVEL, LIBUSB_LOG_LEVEL_WARNING );

  // Open our ADU device that matches our vendor id and product id
  if (pico == 0)
  {
    device_handle_0 = libusb_open_device_with_vid_pid(NULL, VENDOR_ID_0, PRODUCT_ID);

    libusb_set_auto_detach_kernel_driver(device_handle_0, 1);
    // Claim interface 0 on the device
    libusb_claim_interface(device_handle_0, 1);
  }
  else
  {
    device_handle_1 = libusb_open_device_with_vid_pid(NULL, VENDOR_ID_1, PRODUCT_ID);
    libusb_set_auto_detach_kernel_driver(device_handle_1, 1);
    // Claim interface 0 on the device
    libusb_claim_interface(device_handle_1, 1);
  }
  return 0;
}




int initialize_pipes(int fd[num_pipes], int vfd[num_pipes]) {

  char *pipe_path = malloc(15);
  struct stat st_i;

  for (int pipe_id=0; pipe_id<num_pipes; pipe_id++) {
    strncpy(pipe_path, pipe_path_base, 15);
    pipe_path[14] = 48+pipe_channels[pipe_id];
    if (stat(pipe_path, &st_i) == -1)
    {
      if (mkfifo(pipe_path, 0666) == -1)
      {
        perror("Failed to create named pipe");

        use_pipe = 0; // ensure that pipe isn't used if failed
      }
    }

    fd[pipe_id] = open(pipe_path, O_WRONLY | O_NONBLOCK);
    if (fd[pipe_id] == -1)
    {
      printf("current error\n");
      perror("Error opening pipe");

      use_pipe = 0; // ensure that pipe isn't used if failed
    }
  }

  struct stat st[num_pipes];
  for (int pipe_id=0; pipe_id<num_pipes; pipe_id++) {
    sleep(0.1);
    char *v_pipe_path = malloc(16);
    memcpy(v_pipe_path, &v_pipe_path_base, 15);
    v_pipe_path[15] = pipe_channels[pipe_id]+48;

    if (stat(v_pipe_path, &st[pipe_id]) == -1)
    {
      if (mkfifo(v_pipe_path, 0666) == -1)
      {
        perror("Failed to create named pipe");

        // ensure that pipe isn't used - would result in failure
        use_pipe = 0;
      }
    }
    printf("v pipe path: %s\n", v_pipe_path);

    vfd[pipe_id] = open(v_pipe_path, O_WRONLY | O_NONBLOCK);
    if (vfd[pipe_id] == -1)
    {
      printf("voltage error\n");
      perror("Error opening pipe");

      // ensure that pipe isn't used - would result in failure
      use_pipe = 0;
    }
  }

  return 0;
}
















// ----- Code to handle HV data acquisition & storage ----- //

void *acquire_data(void *arguments)

{
  arg_struct *common = arguments;
  float last_output[6]; // State for each channel's filter

  
  int fd[num_pipes];
  int vfd[num_pipes];


  int pipe_initialization_success = initialize_pipes(fd, vfd);




  uint16_t inner_loop = 1;

  char current_char = 'H';
  char voltage_char = 'V';

  char *input_data;
  input_data = (char *)malloc(64 * inner_loop);

  char *voltage_input_data;
  voltage_input_data = (char *)malloc(24);

  float floatval = 0;
  float floatval_voltage = 0;

  uint8_t allow_read = 1;














  // current txt storage info
  time_t seconds;

  uint8_t pico = common->pico;

  float store_all_currents_internal[6][HISTORY_LENGTH];

  current_datafile_time = time(NULL);
  char *filename_I = malloc(50);

  char *current_precursor;
  char *file_suffix = ".txt";
  if (pico == 0) {
    current_precursor = "../../Data/Currents_0_";
    strcpy(filename_I, &current_precursor[0]);
  } else {
    current_precursor = "../../Data/Currents_1_";
    strcpy(filename_I, &current_precursor[0]);
  }
  
  char str_time[10];
  sprintf(str_time, "%i", current_datafile_time);
  strcat(filename_I, str_time);
  strcat(filename_I, file_suffix);

  FILE *fp_I = fopen(filename_I, "a");




  int pico0_init_success = initialize_libusb(0); // initialize libusb connection with pico 0





















  while (1)
  {


    command check_command = parse_pico_queue();
    char current_command = check_command.command_name;
    char current_type = check_command.command_type;
    uint8_t char_parameter = (uint8_t)check_command.char_parameter - 97;
    float float_parameter = check_command.float_parameter;
    int client_addr = check_command.client_addr;

    // check if command is pico type, else do nothing
    if (current_type == 'c')
    {
      pthread_mutex_lock(&usb0_mutex_lock);
      // select proper hv function
      if (current_command == 'k')
      { // trip
        trip(char_parameter, client_addr);
      }
      else if (current_command == 'l')
      { // reset trip
        reset_trip(char_parameter, client_addr);
      }
      else if (current_command == 'm')
      { // disable trip
        disable_trip(char_parameter, client_addr);
      }
      else if (current_command == 'n')
      { // enable trip
        enable_trip(char_parameter, client_addr);
      }
      else if (current_command == 'p')
      { // set trip
        set_trip(char_parameter, float_parameter, client_addr);
      }
      else if (current_command == 'o')
      { // trip status
        trip_status(char_parameter, client_addr);
      }
      else if (current_command == '%')
      { // enable ped
        enable_ped(char_parameter, client_addr);
      }
      else if (current_command == '&')
      { // disable ped
        disable_ped(char_parameter, client_addr);
      }
      pthread_mutex_unlock(&usb0_mutex_lock);
    }

    // check if other pico command needs to be sent


      char *filename_V;

      // fill up array
      for (uint16_t time_index = 0; time_index < HISTORY_LENGTH;)
      {
        if (pico == 0)
        {
          pthread_mutex_lock(&usb0_mutex_lock);
          libusb_bulk_transfer(device_handle_0, 0x02, &current_char, 1, 0, 0);
          libusb_bulk_transfer(device_handle_0, 0x82, input_data, 48, 0, 0);
          pthread_mutex_unlock(&usb0_mutex_lock);
        }
        else
        {
          pthread_mutex_lock(&usb1_mutex_lock);
          libusb_bulk_transfer(device_handle_1, 0x02, &current_char, 1, 0, 0);
          libusb_bulk_transfer(device_handle_1, 0x82, input_data, 48, 0, 0);
          pthread_mutex_unlock(&usb1_mutex_lock);
        }

        // check if new data from SmartSwitch
        floatval = *(float *)&input_data[0];
        if (floatval != -100)
        {

          for (uint32_t i = 0; i < 12; i++)
          {
            floatval = *(float *)&input_data[4 * i];

            if (i < 6)
            {
              common->all_currents[i][time_index] = floatval;
            }
            else
            {
              common->all_currents[i - 6][time_index + 1] = floatval;
            }
          }
          time_index += 2;
        }
      }


      if (pico == 0)
      {
        for (uint8_t i = 0; i < 6; i++)
        {
          currents_0[i] = *common->all_currents[i];
        }
        filename_V = "../Voltages_0.txt";
      }
      else
      {
        for (uint8_t i = 0; i < 6; i++)
        {
          currents_1[i] = *common->all_currents[i];
        }
        filename_V = "../Voltages_1.txt";
      }

      // copy array to storage array
      for (uint8_t channel = 0; channel < 6; channel++)
      {
        for (uint16_t time = 0; time < HISTORY_LENGTH; time++)
        {
          memcpy(&common->all_currents_stored[channel][time], &common->all_currents[channel][time], sizeof(&common->all_currents[channel][time]));
        }
      }
      if (common->array_indicator == 0) {
        uint8_t new = 1;
        memcpy(&common->array_indicator, &new, 1);
        common->array_indicator = 1;
      } else {
        uint8_t new = 0;
        memcpy(&common->array_indicator, &new, 1);
      }




      // ----- Request and store one voltage value -----

      if (pico == 0)
      {
        pthread_mutex_lock(&usb0_mutex_lock);
        libusb_bulk_transfer(device_handle_0, 0x02, &voltage_char, 1, 0, 0);
        libusb_bulk_transfer(device_handle_0, 0x82, voltage_input_data, 24, 0, 0);
        pthread_mutex_unlock(&usb0_mutex_lock);
      }
      else
      {
        pthread_mutex_lock(&usb1_mutex_lock);
        libusb_bulk_transfer(device_handle_1, 0x02, &voltage_char, 1, 0, 0);
        libusb_bulk_transfer(device_handle_1, 0x82, voltage_input_data, 24, 0, 0);
        pthread_mutex_unlock(&usb1_mutex_lock);
      }

      if (pico == 0)
      {
        for (uint32_t i = 0; i < 6; i++)
        {
          floatval_voltage = *(float *)&voltage_input_data[4 * i];
          voltages_0[i] = floatval_voltage;
        }
      }
      else
      {
        for (uint32_t i = 0; i < 6; i++)
        {
          floatval_voltage = *(float *)&voltage_input_data[4 * i];
          voltages_1[i] = floatval_voltage;
        }
      }



      // ----- Save Voltages in txt file -----
      int voltage_write_success = write_voltages(filename_V, voltages_0);

      // ----- Send voltages via GUI pipes -----
      int pipe_voltage_success = write_pipe_voltages(pico, vfd, voltages_0);






  if (current_num_storages >= current_max_storages) {
  

    current_datafile_time = time(NULL);
    current_num_storages = 0;
    fclose(fp_I);

    if (pico == 0) {
      current_precursor = "../../Data/Currents_0_";
      strcpy(filename_I, &current_precursor[0]);
    } else {
      current_precursor = "../../Data/Currents_1_";
      strcpy(filename_I, &current_precursor[0]);
    }
    
    char str_time[10];
    sprintf(str_time, "%i", current_datafile_time);
    strcat(filename_I, str_time);
    strcat(filename_I, file_suffix);


    FILE *fp_I = fopen(filename_I, "a");
    if (fp_I == NULL) {
          printf("Error opening the current file %s", filename_I);
        }

  } else {
    current_num_storages += HISTORY_LENGTH;
  }
  
    

      // save data in current log
      for (uint32_t time_index=0; time_index<HISTORY_LENGTH; time_index++) {
        for (uint8_t channel=0; channel<6; channel++) {
          fprintf(fp_I, "%f ", common->all_currents_stored[channel][time_index]);
        }
        seconds = time(NULL);
        fprintf(fp_I, "%f\n", (float)seconds);
      }


    int pipe_current_success = write_pipe_currents(fd, common->all_currents_stored);




      
    
  }

  fclose(fp_I);
}




int lv_initialization() {
  if (setup_gpio(lv_global_enable) == -1) {
    return -1;
  } else if (write_gpio_value(lv_global_enable, LOW) == -1) {
    return -1;
  }

  for (int i=0; i<6; i++) {
    if (MCP_pinMode(lvpgoodMCP, powerChMap[i], OUTPUT) == -1) {
      return -1;
    }

    if (MCP_pinWrite(lvpgoodMCP, powerChMap[i],0) == -1) {
      return -1;
    }
  }

  int file;
  int i;
  int res;
  int oldvalue;

  char lv_i2cname[20];

  lv_i2cbus = lookup_i2c_bus("3");
  sprintf(lv_i2cname, "/dev/i2c-%d", 3);
  lv_i2c = open_i2c_dev(lv_i2cbus, lv_i2cname, sizeof(lv_i2cname), 0);

  if (lv_i2c < 0) { // return -1 in case of not acquiring file
    return -1;
  }

  return 0;
}



void sigintHandler(int sig_num) {
    /* Reset handler to catch SIGINT next time. 
    Refer http://en.cppreference.com/w/c/program/signal */
    signal(SIGINT, sigintHandler); 

  sleep(0.1);
    

  pthread_cancel(acquisition_thread_0);
  pthread_cancel(command_execution_thread);

  sleep(1);
  libusb_device *device_0 = libusb_get_device(device_handle_0);
  libusb_unref_device(device_0);
  free(device_handle_0);

  
} 



int main( int argc, char **argv ) {
  // initialize queues
  const char *pathname = "/home/mu2e/LVHVBox/CServer/build";
  queue_id = 0;
  queue_key = ftok(pathname, queue_id);
  printf("queue key: %i\n", queue_key);
  msqid = msgget(queue_key, IPC_CREAT);
  printf("msqid: %i\n", msqid);

  pico_queue_id = 1;
  pico_queue_key = ftok(pathname, pico_queue_id);
  pico_msqid = msgget(pico_queue_key, IPC_CREAT);









  hvMCP=(MCP*)malloc(sizeof(struct MCP*));
  lvpgoodMCP=(MCP*)malloc(sizeof(struct MCP*));

  // save time that server started
  start_time = (int) time(NULL);

  signal(SIGINT, sigintHandler); 


  //char *test = load_config("test");
  //printf("test: %s\n",test);


  /**
   * @brief setup SPI comm
   * 
   */

  if ((spiFds = open (spidev, O_RDWR)) < 0){
    printf("Unable to open SPI device: %s\n",spidev);
    return 0;
  }

  if (ioctl (spiFds, SPI_IOC_WR_MODE, &spi_mode)            < 0){
    printf("SPI Mode Change failure: %s\n",spidev);
    return 0;
  }

  if (ioctl (spiFds, SPI_IOC_WR_BITS_PER_WORD, &spi_bpw) < 0){
    printf("SPI BPW Change failure: %s\n",spidev);
    return 0;
  }

  if (ioctl (spiFds, SPI_IOC_WR_MAX_SPEED_HZ, &spi_speed)   < 0){
    printf("SPI Speed Change failure: %s\n",spidev);
    return 0;
  }


/**
 * @brief setup MCPs with their appropriate addresses
 * 
 */
  
// Export the GPIO pins

    if (setup_gpio(lv_mcp_reset) == -1) {
        return 1;
    }




    
    // Turn off the GPIO pin (set it to 1)
    if (write_gpio_value(lv_mcp_reset, 0) == -1) {
        return 1;
    }

    // Turn on the GPIO pin (set it to 1)
    if (write_gpio_value(lv_mcp_reset, 1) == -1) {
        return 1;
    }

  
  if (MCP_setup(hvMCP,2) == -1) {
    return -1;
  } else if (MCP_setup(lvpgoodMCP,1) == -1) {
    return -1;
  }
  

  if (hv_initialization() == -1) {
    return -1;
  } else if (lv_initialization() == -1) {
    return -1;
  }


  FILE *file = fopen(LIVE_STATUS_FILENAME, "w");
  fclose(file);

  for (int i = 0; i < 6; i++) {
    // writes 1
    if (write_fixed_location(LIVE_STATUS_FILENAME, 2 * i, 0) == -1) {
      return -1;
    }
  }

  // ----- initialize pico 0 communications, etc ----- //
  arg_struct args_0;
  args_0.array_indicator = 0;
  args_0.pico = 0;

  // check that pico 0 is available
  int libusb_code = libusb_init(NULL);
  printf("libusb code: %i\n", libusb_code);
  
  device_handle_0 = libusb_open_device_with_vid_pid(NULL, VENDOR_ID_0, PRODUCT_ID);
  if (device_handle_0 == 0) {
    printf("Please connect pico 0\n");
    error_log("Pico 0 not connected");

    return -1;
  }





  

  // ----- initialize pico 1 communications, etc ----- //
  /*
  struct arg_struct args_1;
  args_1.array_indicator = 0;
  args_1.pico = 1;

  // create data acquisition thread
  pthread_t acquisition_thread_1;
  pthread_create(&acquisition_thread_1, NULL, acquire_data, &args_1);

  */
  // create data acquisition thread
  pthread_create(&acquisition_thread_0, NULL, acquire_data, &args_0);
 
  // create statusing thread
  pthread_t status_thread_0;
  pthread_create(&status_thread_0, NULL, live_status, &args_0);

  // create socket initialization thread
  pthread_t socket_creation_thread;
  pthread_create(&socket_creation_thread, NULL, create_connections, NULL);

  // create hv execution thread
  pthread_create(&command_execution_thread, NULL, command_execution, NULL);



  pause();

  

  return 0;
}
