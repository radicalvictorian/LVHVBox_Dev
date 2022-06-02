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
#include "ad5685.h"



#define MCPPINBASE 2000

#define SPISPEED 40000000
#define NSTEPS 100
//#define SPISPEED 320000

AD5685 dac[3];


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






/*
void initialization(){


  wiringPiSetup() ;
  wiringPiSPISetup(0, SPISPEED);


  //bring the MCP out of reset
  pinMode(26, OUTPUT);
  digitalWrite(26, HIGH);

  //setup MCP
  int retc = mcp23s17Setup (MCPPINBASE, 0, 0);
  printf("mcp setup done %d\n",retc);

  //sete RESET to DACs to high
  digitalWrite(MCPPINBASE+7, 1);
  pinMode(MCPPINBASE+7, OUTPUT);

  //sete LDAC to DACs to low
  digitalWrite(MCPPINBASE+3, 0);
  pinMode(MCPPINBASE+3, OUTPUT);



  AD5685_setup(&dac[0], MCPPINBASE, 4, MCPPINBASE, 2, MCPPINBASE, 0);
  AD5685_setup(&dac[1], MCPPINBASE, 5, MCPPINBASE, 2, MCPPINBASE, 0);
  AD5685_setup(&dac[2], MCPPINBASE, 6, MCPPINBASE, 2, MCPPINBASE, 0);

}
*/

void initialize_hv(void)
{
  wiringPiSetup();
  wiringPiSPISetup(0, SPISPEED);

  //bring the MCP out of reset
  pinMode(26, OUTPUT);
  digitalWrite(26, HIGH);

  //setup MCP
  int retc = mcp23s17Setup (MCPPINBASE, 0, 0);
  printf("mcp setup done %d\n",retc);

  //sete RESET to DACs to high
  digitalWrite(MCPPINBASE+7, 1);
  pinMode(MCPPINBASE+7, OUTPUT);

  //sete LDAC to DACs to low
  digitalWrite(MCPPINBASE+3, 0);
  pinMode(MCPPINBASE+3, OUTPUT);



  AD5685_setup(&dac[0], MCPPINBASE, 4, MCPPINBASE, 2, MCPPINBASE, 0);
  AD5685_setup(&dac[1], MCPPINBASE, 5, MCPPINBASE, 2, MCPPINBASE, 0);
  AD5685_setup(&dac[2], MCPPINBASE, 6, MCPPINBASE, 2, MCPPINBASE, 0);
}


/*
int main(int argc, char *argv[])
{
	int opt;
	int cmderr = 0;

	initialization();

	int channel = atoi(argv[1]);
	float value = atof(argv[2]);


	int idac = (int) (channel/4);
	printf(" Chan %i HV idac %i  is set to %7.2f\n", channel, idac, value);


	struct timeval start, end, total ;

	gettimeofday (&start, NULL) ;


	float increment = value*2.3/NSTEPS/1510.;
	float setvalue = 0;
	for (int itick =0; itick < NSTEPS; itick++){
	  usleep(50000);
	  setvalue += increment;
	  AD5685_setdac(&dac[idac],channel%4,setvalue);
	}

	gettimeofday (&end, NULL) ;

	return 0 ;
}
*/

void set_hv(int channel, int value)
{
  int idac = (int) (channel/4);

  float increment = value*2.3/NSTEPS/1510.;
  float setvalue = 0;
  for (int itick =0; itick < NSTEPS; itick++){
    usleep(50000);
    setvalue += increment;
    AD5685_setdac(&dac[idac],channel%4,setvalue);
  }
}