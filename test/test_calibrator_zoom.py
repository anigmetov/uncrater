import sys

import uncrater.Packet_Calibrator

sys.path.append('.')
sys.path.append('./scripter/')
sys.path.append('./commander/')
import matplotlib.pyplot as plt
import os

from typing import List

import argparse
import numpy as np
from test_base import Test
from test_base import pycoreloop as cl
from lusee_script import Scripter
import uncrater as uc
from collections import defaultdict


class Test_CalibratorZoom(Test):
    name = "calibrator_zoom"
    version = 0.1
    description = """ Runs the WV calibrator EM """
    instructions = """ Connect the VW calibrator.  """
    default_options = {
        "mode": "manual",
        "slow": False,
        "freq_start": 5.0375,
        "freq_end": 5.0625,
        "freq_step": 0.000,
        "zoom_navg": 6,
        "pfb_bin": 202,
        "ampl": 1.0,
    }  ## dictinary of options for the test
    options_help = {
        "mode": "manual",
        "slow": "Run the test in slow mode for SSL",
        "freq_start": "First AWG tone frequency [MHz] of the sweep (also the single-tone freq when freq_step<=0)",
        "freq_end": "Last AWG tone frequency [MHz] of the sweep (inclusive)",
        "freq_step": "AWG frequency step [MHz]. If >0, sweep freq_start..freq_end one zoom packet per step; if <=0, take a single tone at freq_start",
        "zoom_navg": "Zoom averaging setting (cal_set_zoom_navg); tune so one main spectrum yields one zoom packet",
        "pfb_bin": "PFB bin index the zoom is centred on (cal_set_pfb_bin)",
        "ampl": "AWG tone amplitude [mVPP]",
    }  ## dictionary of help for the options

    def sweep_frequencies(self):
        """ Return the ordered list of AWG tone settings for the sweep.

        Each entry is either a float frequency [MHz] or None for an AWG-off
        baseline measurement. AWG-off baselines bracket the sweep so the
        baseline can be subtracted in the analysis.
        Returns an empty list when not in sweep mode (freq_step<=0).
        """
        if self.freq_step <= 0:
            return []
        tones = list(np.arange(self.freq_start,
                               self.freq_end + self.freq_step / 2.0,
                               self.freq_step))
        # AWG-off baselines at the beginning and the end.
        return [None] + tones + [None]

    def generate_script(self):
        """ Generates a script for the test """

        S = Scripter()

        S.wait(1)
        S.reset()
        S.wait(3)

        if self.slow:
            S.set_dispatch_delay(120)

        # S.enable_heartbeat(False)
        S.set_Navg(14, 4)

        # Set up the zoom channels based on where AWG is connected     
        S.cal_set_zoom_diff(self.slow, False)
        S.cal_set_zoom_ch(2,1,0,0)

        ### Main spectral engine

        S.set_ana_gain('MMLM')
        for i in range(4):
            S.set_route(i, None, i)

        S.set_bitslice(0, 10)
        for i in range(4):
            S.set_bitslice(i, 24 if i==2 else 19)

        S.cal_set_pfb_bin(self.pfb_bin)
        S.cal_set_zoom_navg(self.zoom_navg)
        S.cal_enable(enable=True, mode=cl.pystruct.CAL_MODE_ZOOM)

        ch = 1

        sweep = self.sweep_frequencies()
        if sweep:
            # Sweep mode: stop/restart the spectrometer at every step so each
            # step produces exactly one main spectrum (and one zoom packet).
            for freq in sweep:
                if freq is None:
                    S.awg_tone(ch, 80.0, 0)  # AWG off -> baseline
                else:
                    S.awg_tone(ch, freq, self.ampl)
                S.cdi_wait_ticks(20)
                S.start()
                S.cdi_wait_spectra(1)
                S.stop()
                S.request_eos()
                S.wait_eos()
        else:
            # Single-tone mode (legacy behaviour).
            S.awg_tone(ch, self.freq_start, self.ampl)
            S.start()
            S.cdi_wait_seconds(60)
            S.stop()

        S.request_eos()
        S.wait_eos()

        return S

    def plot_zoom_spectra(self, zoom_spectra_packets: List[uncrater.Packet_Calibrator.Packet_Cal_ZoomSpectra], figures_dir: str):
        """
        Plot the first 3 packets from zoom_spectra_packets list.
        Each packet gets its own figure with 2x2 subplots showing the 4 numpy arrays.
        """
        fig, axes = plt.subplots(3, 4, figsize=(16, 12))
        fig.suptitle('Zoom Spectra Data', fontsize=16, fontweight='bold')

        # Plot data for first 3 packets
        for packet_idx in range(min(3, len(zoom_spectra_packets))):
            packet = zoom_spectra_packets[packet_idx]

            # Row for this packet
            row = packet_idx

            axes[row, 0].plot(packet.AA)
            axes[row, 0].set_title(f'Packet {packet_idx}: Autocorrelation Channel 1')
            axes[row, 0].grid(True, alpha=0.3)

            axes[row, 1].plot(packet.BB)
            axes[row, 1].set_title(f'Packet {packet_idx}: Autocorrelation Channel 2')
            axes[row, 1].grid(True, alpha=0.3)

            axes[row, 2].plot(packet.ABR)
            axes[row, 2].set_title(f'Packet {packet_idx}: Correlation Real')
            axes[row, 2].grid(True, alpha=0.3)

            axes[row, 3].plot(packet.ABI)
            axes[row, 3].set_title(f'Packet {packet_idx}: Correlation Imaginary')
            axes[row, 3].grid(True, alpha=0.3)

        # Adjust layout to prevent overlap
        plt.tight_layout()

        # Save to PDF
        plt.savefig(os.path.join(figures_dir, 'zoom_spectra.pdf'), format='pdf', dpi=300, bbox_inches='tight')
        plt.close()

    def plot_spectra(self, spectra, figures_dir):
        fig_sp, ax_sp = plt.subplots(4, 4, figsize=(12, 12))
        freq = np.arange(1, 2048) * 0.025

        for i, S in enumerate(spectra):
            for c in range(16):
                x, y = c // 4, c % 4

                if c < 4:
                    data = S[c].data[1:]
                    ax_sp[x][y].plot(freq, data, label=f"{i}")
                    ax_sp[x][y].set_xscale('log')
                    ax_sp[x][y].set_yscale('log')
                else:
                    data = S[c].data[:400] * freq[:400] ** 2
                    ax_sp[x][y].plot(freq[:400], data)
            break
        for j in range(4):
            ax_sp[3][j].set_xlabel('frequency [MHz]')
            ax_sp[j][0].set_ylabel('power [uncalibrated]')

        fig_sp.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'spectra.pdf'), format='pdf', dpi=300, bbox_inches='tight')
        plt.close()

    def save_zoom_sweep(self, C: uc.Collection, work_dir):
        """ Read all zoom spectra packets, match them to the AWG settings used
        in the sweep and save an npz file of zoom_spectra at each AWG setting.

        Also stores the main spectral product (all 16 channels) evaluated at the
        zoom ``pfb_bin`` for every step. AWG-off baselines (bracketing the sweep)
        are averaged and subtracted from the tone measurements.
        Returns the assembled data dict (or None if there is nothing to save).
        """
        sweep = self.sweep_frequencies()
        packets = C.zoom_spectra_packets

        if len(packets) != len(sweep):
            print(f"Warning: number of zoom packets ({len(packets)}) does not "
                  f"match number of AWG settings ({len(sweep)}); "
                  f"matching positionally up to the shorter length.")
        n = min(len(packets), len(sweep))
        if n == 0:
            return None

        # Stack the four products for the n matched packets.
        AA = np.array([packets[i].AA for i in range(n)])
        BB = np.array([packets[i].BB for i in range(n)])
        ABR = np.array([packets[i].ABR for i in range(n)])
        ABI = np.array([packets[i].ABI for i in range(n)])
        pfb_bin = np.array([packets[i].pfb_bin for i in range(n)])

        # freqs: NaN marks an AWG-off baseline measurement.
        freqs = np.array([np.nan if sweep[i] is None else sweep[i]
                          for i in range(n)])
        is_baseline = np.isnan(freqs)

        # Main spectral product at the zoom pfb_bin, all 16 channels, per step.
        # C.spectra entries are dicts {"meta":..., 0..15: spectrum}; match
        # positionally to the steps and fill missing channels/steps with NaN.
        main_pfb = np.full((n, 16), np.nan)
        for i in range(min(n, len(C.spectra))):
            sp = C.spectra[i]
            for c in range(16):
                pkt = sp.get(c)
                if pkt is not None and self.pfb_bin < len(pkt.data):
                    main_pfb[i, c] = pkt.data[self.pfb_bin]

        # Average baselines (if any) and subtract from every measurement.
        baseline = {}
        for key, arr in (('AA', AA), ('BB', BB), ('ABR', ABR), ('ABI', ABI)):
            if is_baseline.any():
                baseline[key] = arr[is_baseline].mean(axis=0)
            else:
                baseline[key] = np.zeros(arr.shape[1])

        data = dict(
            freqs=freqs,
            is_baseline=is_baseline,
            pfb_bin=pfb_bin,
            ampl=self.ampl,
            zoom_navg=self.zoom_navg,
            main_pfb=main_pfb,
            AA=AA, BB=BB, ABR=ABR, ABI=ABI,
            AA_sub=AA - baseline['AA'],
            BB_sub=BB - baseline['BB'],
            ABR_sub=ABR - baseline['ABR'],
            ABI_sub=ABI - baseline['ABI'],
            baseline_AA=baseline['AA'], baseline_BB=baseline['BB'],
            baseline_ABR=baseline['ABR'], baseline_ABI=baseline['ABI'],
        )

        out_file = os.path.join(work_dir, 'zoom_sweep.npz')
        np.savez(out_file, **data)
        print(f"Saved zoom sweep ({n} settings) to {out_file}")
        return data

    def plot_waterfall(self, figures_dir, data=None, packets=None):
        """ Waterfall (AWG step / packet index vs zoom bin) of the four zoom
        products. In sweep mode pass the assembled ``data`` dict (rows labelled
        by AWG tone frequency); otherwise pass the raw zoom ``packets`` list
        (rows labelled by packet index). """
        if data is not None:
            freqs = data['freqs']
            AA, BB, ABR, ABI = data['AA'], data['BB'], data['ABR'], data['ABI']
            ylabels = ['off' if np.isnan(f) else f'{f:.5f}' for f in freqs]
            ylabel = 'AWG tone [MHz]'
        else:
            packets = packets or []
            AA = np.array([p.AA for p in packets])
            BB = np.array([p.BB for p in packets])
            ABR = np.array([p.ABR for p in packets])
            ABI = np.array([p.ABI for p in packets])
            ylabels = [str(i) for i in range(len(packets))]
            ylabel = 'packet index'

        n = len(ylabels)
        products = [('AA', AA), ('BB', BB), ('ABR', ABR), ('ABI', ABI)]

        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        fig.suptitle('Zoom Spectra Waterfall', fontsize=16, fontweight='bold')

        for ax, (name, arr) in zip(axes.flat, products):
            ax.set_title(name)
            ax.set_xlabel('zoom bin')
            ax.set_ylabel(ylabel)
            if n == 0:
                # No zoom packets: emit an empty placeholder so the report builds.
                continue
            im = ax.imshow(arr, aspect='auto', origin='lower',
                           interpolation='nearest',
                           extent=[0, arr.shape[1], 0, n])
            # Avoid an unreadable axis when there are many rows.
            if n <= 40:
                ax.set_yticks(np.arange(n) + 0.5)
                ax.set_yticklabels(ylabels, fontsize=6)
            fig.colorbar(im, ax=ax)

        plt.tight_layout()
        plt.savefig(os.path.join(figures_dir, 'waterfall.pdf'), format='pdf',
                    dpi=300, bbox_inches='tight')
        plt.close()

    def analyze(self, C: uc.Collection, uart, commander, figures_dir):
        """ Analyzes the results of the test.
            Returns true if test has passed.
        """
        self.results = {}
        passed = True

        self.results['packets_received'] = len(C.cont)
        self.get_versions(C)

        crc_ok = C.all_spectra_crc_ok()
        if not crc_ok:
            passed = False

        has_all_products = C.has_all_products()
        if not has_all_products:
            passed = False

        self.results['zoom_sp_received'] = len(C.zoom_spectra_packets)

        if not len(C.zoom_spectra_packets) > 0:
            passed = False

        self.results['sp_num'] = len(C.spectra)

        if len(C.spectra) > 0:
            self.results['sp_crc'] = int(crc_ok)
            self.results['sp_all'] = int(has_all_products)
            self.results["meta_error_free"] = C.all_meta_error_free()
        else:
            self.results['sp_crc'] = 0
            self.results['sp_all'] = 0
            self.results["meta_error_free"] = 0

        # In sweep mode, save the per-AWG-setting zoom spectra to npz and make a
        # waterfall plot labelled by AWG tone. Otherwise still make a waterfall
        # of all zoom packets (labelled by packet index) for the report.
        if self.sweep_frequencies():
            # figures_dir is <work_dir>/report/Figures; save npz in <work_dir>.
            work_dir = os.path.dirname(os.path.dirname(figures_dir))
            data = self.save_zoom_sweep(C, work_dir)
            n_saved = 0 if data is None else len(data['freqs'])
            self.results['sweep_settings'] = n_saved
            if data is None:
                passed = False
                self.plot_waterfall(figures_dir, packets=C.zoom_spectra_packets)
            else:
                self.plot_waterfall(figures_dir, data=data)
        else:
            self.plot_waterfall(figures_dir, packets=C.zoom_spectra_packets)

        self.results['result'] = int(passed)
        self.plot_zoom_spectra(C.zoom_spectra_packets, figures_dir)
        self.plot_spectra(C.spectra, figures_dir)
