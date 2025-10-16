/**
 * @file drs4_fe.cpp
 * @brief MIDAS frontend for the DRS4 eval board.
 *
 * This frontend handles the configuration and readout of the DRS4 eval board.
 *
 * @details
 * Key functionalities:
 * - Configuration
 * - Readout
 *
 * @author
 * Marius Snella Köppel
 * @date
 * 2025-10-16
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#include <sstream>
#include <iomanip>
#include <string>

#include <iostream>
#include <list>

#include <math.h>

#ifdef _MSC_VER

#include <windows.h>

#elif defined(OS_LINUX)

#define O_BINARY 0

#include <unistd.h>
#include <ctype.h>
#include <sys/ioctl.h>
#include <errno.h>

#define DIR_SEPARATOR '/'

#endif

#include "strlcpy.h"

// clang-format off
#include "midas.h"
// clang-format on
#include "mcstd.h"
#include "mfe.h"
#include "msystem.h"
#include "odbxx.h"

#include "DRS.h"


// MIDAS settings
const char* frontend_name = "DRS4 FE";
const char* frontend_file_name = __FILE__;
BOOL equipment_common_overwrite = TRUE;

// DRS4 settings
DRS *drsp = nullptr;
DRSBoard *board = nullptr;
float time_array[8][1024];
float wave_array[8][1024];
int nBoards;


int init_drs4(DRS& drs) {

    /* show any found board(s) */
    for (int i=0; i < drs.GetNumberOfBoards(); i++) {
        board = drs.GetBoard(i);
        printf("Found DRS4 evaluation board, serial #%d, firmware revision %d\n", 
            board->GetBoardSerialNumber(), board->GetFirmwareVersion());
    }

    /* exit if no board found */
    nBoards = drs.GetNumberOfBoards();
    if (nBoards == 0) {
        printf("No DRS4 evaluation board found\n");
        return FE_ERR_DRIVER;
    }

    /* continue working with first board only */
    board = drs.GetBoard(0);

    /* initialize board */
    board->Init();

    /* set sampling frequency */
    board->SetFrequency(5, true);

    /* enable transparent mode needed for analog trigger */
    board->SetTranspMode(1);

    /* set input range to -0.5V ... +0.5V */
    board->SetInputRange(0);

    /* use following line to set range to 0..1V */
    //board->SetInputRange(0.5);

    /* use following line to turn on the internal 100 MHz clock connected to all channels  */
    //board->EnableTcal(1);

    /* use following lines to enable hardware trigger on CH1 at 50 mV positive edge */
    if (board->GetBoardType() >= 8) {        // Evaluaiton Board V4&5
        board->EnableTrigger(1, 0);           // enable hardware trigger
        board->SetTriggerConfig(1<<0);        // set CH1 as source
    } else if (board->GetBoardType() == 7) { // Evaluation Board V3
        board->EnableTrigger(0, 1);           // lemo off, analog trigger on
        board->SetTriggerConfig(1);           // use CH1 as source
    }
    board->SetTriggerLevel(0.025);            // 0.025 V
    board->SetTriggerPolarity(false);        // positive edge

    /* use following lines to set individual trigger levels */
    //board->SetIndividualTriggerLevel(1, 0.1);
    //board->SetIndividualTriggerLevel(2, 0.2);
    //board->SetIndividualTriggerLevel(3, 0.3);
    //board->SetIndividualTriggerLevel(4, 0.4);
    //board->SetTriggerSource(15);

    board->SetTriggerDelayNs(0);             // zero ns trigger delay

    /* use following lines to enable the external trigger */
    //if (board->GetBoardType() >= 8) {        // Evaluaiton Board V4&5
    //   board->EnableTrigger(1, 0);           // enable hardware trigger
    //   board->SetTriggerConfig(1<<4);        // set external trigger as source
    //} else {                             // Evaluation Board V3
    //   board->EnableTrigger(1, 0);           // lemo on, analog trigger off
    //}

    return SUCCESS;
}

int begin_of_run() { return SUCCESS; }

int end_of_run() { return SUCCESS; }

int frontend_exit_user() { return SUCCESS; }

int read_stream_thread(void*) {

    // get board
    DRS& drs = *drsp;
    board = drs.GetBoard(0);

    // tell framework that we are alive
    signal_readout_thread_active(0, TRUE);

    // obtain ring buffer for inter-thread data exchange
    int rbh = get_event_rbh(0);
    int status;

    // actuall readout loop
    while (is_readout_thread_enabled()) {
        // don't readout events if we are not running
        if (!readout_enabled()) {
            // printf("Not running!\n");
            //  do not produce events when run is stopped
            ss_sleep(10);  // don't eat all CPU
            continue;
        }

        // get midas buffer
        void* event = nullptr;
        // obtain buffer space with 10 ms timeout
        status = rb_get_wp(rbh, &event, 10);

        // just try again if buffer has no space
        if (status == DB_TIMEOUT) {
            // printf("WARNING: DB_TIMEOUT\n");
            ss_sleep(10);  // don't eat all CPU
            continue;
        }

        // stop if there is an error in the ODB
        if (status != DB_SUCCESS) {
            printf("ERROR: rb_get_wp -> rb_status != DB_SUCCESS\n");
            break;
        }

        /* start board (activate domino wave) */
        board->StartDomino();

        /* wait for trigger */
        printf("Waiting for trigger...\n");

        while (board->IsBusy());

        /* read all waveforms */
        board->TransferWaves(0, 8);

        /* read time (X) array of first channel in ns */
        board->GetTime(0, 0, board->GetTriggerCell(0), time_array[0]);

        /* decode waveform (Y) array of first channel in mV */
        board->GetWave(0, 0, wave_array[0]);

        /* read time (X) array of second channel in ns
        Note: On the evaluation board input #1 is connected to channel 0 and 1 of
        the DRS chip, input #2 is connected to channel 2 and 3 and so on. So to
        get the input #2 we have to read DRS channel #2, not #1. */
        board->GetTime(0, 2, board->GetTriggerCell(0), time_array[1]);

        /* decode waveform (Y) array of second channel in mV */
        board->GetWave(0, 2, wave_array[1]);

        /* Save waveform: X=time_array[i], Yn=wave_array[n][i] */
        printf("Event ----------------------\n  t1[ns]  u1[mV]  t2[ns] u2[mV]\n");
        for (int i = 0; i < board->GetChannelDepth(); i++)
            printf("%7.3f %7.1f %7.3f %7.1f\n", time_array[0][i], wave_array[0][i], time_array[1][i], wave_array[1][i]);

        /* print some progress indication */
        printf("\rEvent read successfully %i\n", board->GetNumberOfChannels());

        // send time stamp data to MIDAS
        int idx = 0;
        auto eventHeader = reinterpret_cast<EVENT_HEADER*>(event);
        bm_compose_event_threadsafe(eventHeader, 666, 0, 0, &equipment[0].serial_number);
        auto bankHeader = reinterpret_cast<BANK_HEADER*>(eventHeader + 1);
        bk_init32a(bankHeader); // create MIDAS bank
        // write time
        for (int ch = 0; ch < 4; ch++) {
            char* data = nullptr;
            std::ostringstream oss;
            oss << "TC" << std::setw(2) << std::setfill('0') << ch;
            std::string bank_name = oss.str(); // "DC03"
            bk_create(bankHeader, bank_name.c_str(), TID_FLOAT, reinterpret_cast<void**>(&data));
            memcpy(data, &time_array[ch], sizeof(time_array[ch]));
            data += sizeof(time_array[ch]);
            bk_close(bankHeader, data);
        }
        // write ToT
        for (int ch = 0; ch < 4; ch++) {
            char* data = nullptr;
            std::ostringstream oss;
            oss << "CC" << std::setw(2) << std::setfill('0') << ch;
            std::string bank_name = oss.str(); // "DC03"
            bk_create(bankHeader, bank_name.c_str(), TID_FLOAT, reinterpret_cast<void**>(&data));
            memcpy(data, &wave_array[ch], sizeof(wave_array[ch]));
            data += sizeof(wave_array[ch]);
            bk_close(bankHeader, data);
        }
        eventHeader->data_size = bk_size(bankHeader);
        rb_increment_wp(rbh, sizeof(EVENT_HEADER) + eventHeader->data_size); // in byte length
    }
    return SUCCESS;
}

int frontend_init() {

    // end and start of run
    install_begin_of_run(begin_of_run);
    install_end_of_run(end_of_run);
    install_frontend_exit(frontend_exit_user);

    /* do initial scan */
    drsp = new DRS();
    int status = init_drs4(*drsp);
    if (status != SUCCESS)
        return FE_ERR_DRIVER;

    // create ring buffer for readout thread
    create_event_rb(0);

    // create readout thread
    ss_thread_create(read_stream_thread, NULL);

    // set write cache to 10MB
    // set_cache_size("SYSTEM", 10000000);

    return SUCCESS;
}

EQUIPMENT equipment[] = {{
    "DRS4 FE",     /* equipment name */
    {666, 0, /* event ID, trigger mask */
    "SYSTEM",        /* event buffer */
    EQ_USER,         /* equipment type */
    0,               /* event source */
    "MIDAS",         /* format */
    TRUE,            /* enabled */
    RO_RUNNING,      /* read always, except during
                        transistions and update ODB */
    1000,            /* read every 1 sec */
    0,               /* stop run after this event limit */
    0,               /* number of sub events */
    0,               /* log history every event */
    "", "", ""},
    NULL, /* readout routine */
},
{""}};
