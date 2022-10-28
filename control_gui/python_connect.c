#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <sys/time.h>
#include <math.h>
#include <unistd.h>
#include <termios.h>

#include <wiringPi.h>
#include <wiringPiSPI.h>
#include <mcp23x0817.h>
#include <mcp23s17.h>
#include <softPwm.h>
#include <linux/spi/spidev.h>
#include <dac8164.h>

#define MCPPINBASE 2000

#define SPISPEED 40000000
#define NSTEPS 200
#define SPICS 0
//#define SPISPEED 320000

DAC8164 dac[3];


int mygetch ( void )
{
  int ch;
  struct termios oldt, newt;

  tcgetattr ( STDIN_FILENO, &oldt );
  newt = oldt;
  newt.c_lflag &= ~( ICANON | ECHO );
  tcsetattr ( STDIN_FILENO, TCSANOW, &newt );
  ch = getchar();
  tcsetattr ( STDIN_FILENO, TCSANOW, &oldt );

  return ch;
}


void initialization(){
  wiringPiSetup();
  wiringPiSPISetup(SPICS, SPISPEED);

  //bring the MCP out of reset
  pinMode(26, OUTPUT);
  digitalWrite(26, HIGH);

  //setup MCP
  int retc = mcp23s17Setup (MCPPINBASE, SPICS, 0);
  printf("mcp setup done %d\n",retc);

  //sete RESET to DACs to high
  digitalWrite (MCPPINBASE+7, 0);
  pinMode(MCPPINBASE+7, OUTPUT);

  //set LDAC to DACs to low
  digitalWrite (MCPPINBASE+3, 0);
  pinMode(MCPPINBASE+3, OUTPUT);

  DAC8164_setup (&dac[0], MCPPINBASE, 4, 2, 0, -1, -1);
  DAC8164_setup (&dac[1], MCPPINBASE, 5, 2, 0, -1, -1);
  DAC8164_setup (&dac[2], MCPPINBASE, 6, 2, 0, -1, -1);
}


// set_hv()
// ========
void set_hv(int channel, int value)
{

    float alpha = 1.;
  if ( channel == 0 ) alpha = 0.9055;
  if ( channel == 1 ) alpha = 0.9073;
  if ( channel == 2 ) alpha = 0.9051;
  if ( channel == 3 ) alpha = 0.9012;
  if ( channel == 4 ) alpha = 0.9012;
  if ( channel == 5 ) alpha = 0.9034;
  if ( channel == 6 ) alpha = 0.9009;
  if ( channel == 7 ) alpha = 0.9027;
  if ( channel == 8 ) alpha = 0.8977;
  if ( channel == 9 ) alpha = 0.9012;
  if ( channel == 10 ) alpha = 0.9015;
  if ( channel == 11 ) alpha = 1.;  // BURNED BOARD - FIX ME!!

  int idac = (int) (channel/4);

  uint32_t digvalue = ( (int) (alpha * 16383.*(value*2.3/(1510*2.5)))) & 0x3FFF;
  printf("%d\n",digvalue);

  DAC8164_writeChannel(&dac[idac], channel, digvalue);
}


// rampup_hv()
// ===========
void rampup_hv(int channel, int value)
{
  int idac = (int) (channel/4);

  float alpha = 1.;
  if ( channel == 0 ) alpha = 0.9055;
  if ( channel == 1 ) alpha = 0.9073;
  if ( channel == 2 ) alpha = 0.9051;
  if ( channel == 3 ) alpha = 0.9012;
  if ( channel == 4 ) alpha = 0.9012;
  if ( channel == 5 ) alpha = 0.9034;
  if ( channel == 6 ) alpha = 0.9009;
  if ( channel == 7 ) alpha = 0.9027;
  if ( channel == 8 ) alpha = 0.8977;
  if ( channel == 9 ) alpha = 0.9012;
  if ( channel == 10 ) alpha = 0.9015;
  if ( channel == 11 ) alpha = 1.;  // BURNED BOARD - FIX ME!!
  

  float increment = value*2.3/NSTEPS/1510.;
  float setvalue = 0;

  for (int itick =0; itick < NSTEPS; itick++){
    usleep(50000);
    setvalue += increment;
    uint32_t digvalue = ( (int) (alpha * 16383.*(setvalue/2.5))) & 0x3FFF;
    //printf("Test %d \n",digvalue);
    
    DAC8164_writeChannel(&dac[idac], channel, digvalue);
  }
}


// Main function
// =============
int main(int argc, char *argv[])
{
  /*
  while((opt = getopt(argc, argv, “:if:lrx”)) != -1)
  {
    switch(opt)
    {
      case ‘i’:
      case ‘l’:
      case ‘r’:
        printf(“option: %c\n”, opt);
        break;
      case ‘f’:
        printf(“filename: %s\n”, optarg);
        break;
      case ‘:’:
        printf(“option needs a value\n”);
        break;
      case ‘?’:
        printf(“unknown option: %c\n”, optopt);
        break;
    }
  }
  */

  initialization();

  int channel = atoi(argv[1]);
  float value = atof(argv[2]);

  value = value*2.3/1510.;
  int idac = (int) (channel/4);
  printf(" Channel %i HV idac %i is set to %7.2f\n", channel, idac, value);

  return 0;
}
