/********************************************************************\

  Name:         drs_scaler.cpp
  Created by:   Stefan Ritt

  Contents:     Wrapper function to read scalers via Labview

  $Id: drs_scaler.cpp 21293 2014-03-19 16:36:44Z ritt $

\********************************************************************/

#include <math.h>

#ifdef _MSC_VER

#include <windows.h>

#elif defined(OS_LINUX)

#include <unistd.h>
#include <ctype.h>
#include <sys/ioctl.h>
#include <errno.h>

#endif

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "DRS.h"

#if defined(_MSC_VER)
#define EXPRT __declspec(dllexport)
#else
#define EXPRT
#endif

#ifdef __cplusplus
extern "C" {
#endif

void EXPRT scaler(unsigned int *s1, unsigned int *s2, unsigned int *s3, unsigned int *s4);

#ifdef __cplusplus
};
#endif

/*------------------------------------------------------------------*/

void scaler(unsigned int *s1, unsigned int *s2, unsigned int *s3, unsigned int *s4)
{
   static DRS *drs = NULL;
   
   if (drs == NULL) {
      drs = new DRS();
   }
   
   if (drs->GetNumberOfBoards()> 0) {
      DRSBoard *b = drs->GetBoard(0);
      *s1 = b->GetScaler(0);
      *s2 = b->GetScaler(1);
      *s3 = b->GetScaler(2);
      *s4 = b->GetScaler(3);
   } else {
      *s1 = -1;
      *s2 = -1;
      *s3 = -1;
      *s4 = -1;
   }
}

/*------------------------------------------------------------------*/

int main()
{
   unsigned int s1, s2, s3, s4;
   
   scaler(&s1, &s2, &s3, &s4);
   printf("%d %d %d %d\n", s1, s2, s3, s4);
   
   return 1;
}
