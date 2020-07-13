import pygame
from pygame import surface
import pygame_gui

from AppManager.app import app

from config_reader import cfg

from . import turbo_colormap
from . import FFTData

class WaterfallDisplay(app):
    REL_BANDWIDTHS = {
        1200000: range(100000, 600001, 100000),
        600000: range(100000, 300001, 100000),
        300000: range(100000, 300001, 100000),
        150000: range(100000, 300001, 100000),
        75000: range(100000, 300001, 100000),
        37500: range(100000, 300001, 100000),
        18750: range(100000, 300001, 100000)
    }

    def __init__(self, bounds, config, display):
        super().__init__(bounds, config, display)

        self.decimate_zoom = True

        BUTTON_Y = cfg.display.DISPLAY_H - self.config.BUTTON_HEIGHT
        self.button_zoom_in = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(
                0, BUTTON_Y,
                128, self.config.BUTTON_HEIGHT
            ),
            text="Zoom In",
            manager=self.gui
        )
        self.button_zoom_out = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(
                128, BUTTON_Y,
                128, self.config.BUTTON_HEIGHT
            ),
            text="Zoom Out",
            manager=self.gui
        )
        self.button_absmode = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(
                cfg.display.DISPLAY_W - 128,
                BUTTON_Y,
                128, self.config.BUTTON_HEIGHT
            ),
            text="Relative Mode",
            manager=self.gui
        )
        self.button_zoommode = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(
                cfg.display.DISPLAY_W - 256,
                BUTTON_Y,
                128, self.config.BUTTON_HEIGHT
            ),
            text="FFT Zoom",
            manager=self.gui
        )
        if self.decimate_zoom:
            # preserve text when disabled as FFT Zoom
            self.button_zoommode.set_text("Decimate Zoom")
        self.label_status = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(
                256 + 1, BUTTON_Y + 1,
                cfg.display.DISPLAY_W - 512 - 2, self.config.BUTTON_HEIGHT - 2
            ),
            text='',
            manager=self.gui
        )

        fftd = FFTData.FFTData(
            provider=config.SAMPLE_PROVIDER,
            config=config
        )

        self.X, self.Y, self.W, self.H = bounds
        self.WF_Y = self.Y + self.config.GRAPH_HEIGHT
        self.WF_H = self.H - self.config.GRAPH_HEIGHT - self.config.BUTTON_HEIGHT

        self.waterfall_surf = surface.Surface((self.W, self.WF_H))
        self.graph_surf = surface.Surface((self.W, self.config.GRAPH_HEIGHT))
        self.rf = fftd

        self.num_fft_bins = None
        self.display_bandwidth = None

        self.absmode = False
        self.abs_freq_low = 7000000
        self.abs_freq_high = 7300000

        self.rel_bandwidth_index = 0
        self.rel_bandwidth = list(self.REL_BANDWIDTHS.keys())[self.rel_bandwidth_index]
        self.update_status()

    def update_status(self):
        if self.rel_bandwidth > 1000000:
            relbw = f"{self.rel_bandwidth/1000000}M"
        else:
            relbw = f"{self.rel_bandwidth/1000}k"
        self.label_status.set_text(f"BW: {relbw}")

    def process_events(self, e):
        super().process_events(e)
        if e.type == pygame.USEREVENT and e.user_type == pygame_gui.UI_BUTTON_PRESSED:
            if e.ui_element == self.button_zoom_in:
                self.rel_bandwidth_index += 1
                rel_bw_list = list(self.REL_BANDWIDTHS.keys())
                self.rel_bandwidth = rel_bw_list[self.rel_bandwidth_index % len(self.REL_BANDWIDTHS)]
                self.update_status()
            elif e.ui_element == self.button_zoom_out:
                self.rel_bandwidth_index -= 1
                rel_bw_list = list(self.REL_BANDWIDTHS.keys())
                self.rel_bandwidth = rel_bw_list[self.rel_bandwidth_index % len(self.REL_BANDWIDTHS)]
                self.update_status()
            elif e.ui_element == self.button_absmode:
                self.absmode = not self.absmode
                if self.absmode:
                    self.button_absmode.set_text("Absolute Mode")
                    self.button_zoom_in.disable()
                    self.button_zoom_out.disable()
                    self.button_zoommode.disable()
                else:
                    self.button_absmode.set_text("Relative Mode")
                    self.button_zoom_in.enable()
                    self.button_zoom_out.enable()
                    self.button_zoommode.enable()
            elif e.ui_element == self.button_zoommode:
                self.decimate_zoom = not self.decimate_zoom
                self.button_zoommode.set_text(
                    "Decimate Zoom" if self.decimate_zoom else "FFT Zoom"
                )

    def draw_wf(self, fft, screen):
        self.waterfall_surf.scroll(0, 1)
        self.waterfall_surf.lock()
        for i in range(self.W):
            pixel_colour = turbo_colormap.interpolate_or_clip(fft[i])
            pixel_colour = [int(c*255) for c in pixel_colour]
            self.waterfall_surf.set_at((i, 0), pixel_colour)
        self.waterfall_surf.unlock()

        screen.blit(self.waterfall_surf, (self.X, self.WF_Y), area=(0, 0, self.W, self.WF_H))

    def freq_to_x(self, freq):
        if self.absmode:
            centre_freq = (self.abs_freq_low + self.abs_freq_high) // 2
        else:
            centre_freq = self.config.CURRENT_FREQ
        centre_pixel = self.bounds.w / 2
        hz_per_pixel = (self.display_bandwidth) / float(self.bounds.w)

        return centre_pixel + int((freq - centre_freq) / hz_per_pixel)

    def draw_marker(self, freq, screen, highlight=False, relative=False):
        x = self.freq_to_x(freq)
        font = pygame.font.Font(None, 24)

        text_colour = (255, 0, 0) if highlight else (0, 255, 255)
        line_colour = (255, 0, 0) if highlight else (0, 128, 0)

        label = f"{int(freq/1000)}" if not relative \
            else f"{(freq-self.config.CURRENT_FREQ)/1000:+.1f}k".replace(".0", "")

        text = font.render(label, True, text_colour)
        text_w = text.get_width()
        text_h = text.get_height()

        text_x = max(min(x-(text_w/2), self.bounds.w - text_w), 0)
        screen.blit(text, (text_x, self.Y))

        if x > 0 and x < self.bounds.w:
            pygame.draw.line(screen, line_colour, (x, self.Y + text_h), (x, self.Y + self.config.GRAPH_HEIGHT + self.WF_H))

    def fade(self):
        # this is too slow to use
        arr = pygame.surfarray.pixels3d(self.graph_surf)
        for x, col in enumerate(arr):
            for y, pix in enumerate(col):
                arr[x][y] = [pix[1]*0.3, pix[1]*0.3, pix[1]*0.3]

    def draw_graph(self, fft, screen):
        #self.fade()
        #self.graph_surf.unlock()

        self.graph_surf.fill((0, 0, 0))

        pixels_25k = int(25000 / self.display_bandwidth * self.bounds.w)
        left_offset = int(self.bounds.w / 2) % pixels_25k

        for i in range(left_offset, self.bounds.w, pixels_25k):
            pygame.draw.line(self.graph_surf, (64, 64, 64), (i, 0), (i, self.config.GRAPH_HEIGHT))

        for i, j in zip(range(self.W), range(1, self.W)):
            try:
                this_y = self.config.GRAPH_HEIGHT - int(fft[i] * float(self.config.GRAPH_HEIGHT))
                next_y = self.config.GRAPH_HEIGHT - int(fft[j] * float(self.config.GRAPH_HEIGHT))
            except OverflowError:
                continue
            pygame.draw.line(self.graph_surf, (0, 255, 0), (i, this_y), (j, next_y))

        screen.blit(
            self.graph_surf,
            (self.X, self.Y),
            area=(0, 0, self.W, self.config.GRAPH_HEIGHT)
        )

    def draw(self, screen):
        total_fft_bw = (self.config.SAMPLE_RATE)
        if self.absmode: # absolute frequency display
            self.display_bandwidth = self.abs_freq_high - self.abs_freq_low
            self.num_fft_bins = int((total_fft_bw / self.display_bandwidth) * self.bounds.w)

            centre_freq = self.config.CURRENT_FREQ
            centre_bin = self.num_fft_bins // 2
            hz_per_pixel = total_fft_bw / float(self.num_fft_bins)

            leftside_bin = centre_bin + int((self.abs_freq_low - centre_freq) / hz_per_pixel)

            fft = self.rf.fft(self.num_fft_bins)[::-1][leftside_bin:]

            fft = (fft - self.config.RF_MIN) / (self.config.RF_MAX - self.config.RF_MIN)
        else:
            self.display_bandwidth = self.rel_bandwidth
            if self.decimate_zoom:
                decimate_factor = int(self.config.SAMPLE_RATE / self.rel_bandwidth)

                fft = self.rf.fft(self.bounds.w, decimate=decimate_factor)
            else:
                self.num_fft_bins = int((total_fft_bw / self.display_bandwidth) * self.bounds.w)

                centre_freq = self.config.CURRENT_FREQ
                centre_bin = self.num_fft_bins // 2
                hz_per_pixel = total_fft_bw / float(self.num_fft_bins)

                leftside_bin = centre_bin + \
                    int((centre_freq - (self.rel_bandwidth / 2) - centre_freq) / hz_per_pixel)

                fft = self.rf.fft(self.num_fft_bins)[::-1][leftside_bin:]
            fft = (fft - self.config.RF_MIN) / (self.config.RF_MAX - self.config.RF_MIN)

        self.draw_wf(fft, screen)
        self.draw_graph(fft, screen)
        self.gui.draw_ui(screen)

        if self.absmode:
            self.draw_marker(self.config.CURRENT_FREQ, screen, highlight=True)
            self.draw_marker(7000000, screen)
            self.draw_marker(7100000, screen)
            self.draw_marker(7200000, screen)
            self.draw_marker(7300000, screen)
        else:
            self.draw_marker(self.config.CURRENT_FREQ, screen, highlight=True, relative=True)
            #for m in self.REL_BANDWIDTHS[self.rel_bandwidth]:
            #    self.draw_marker(config.CURRENT_FREQ + m, screen, relative=True)
            #    self.draw_marker(config.CURRENT_FREQ - m, screen, relative=True)
        return True

    def keydown(self, k, m):
        if k == 'up' and not m & pygame.KMOD_SHIFT:
            self.config.RF_MAX += 10
            print(f"rf_max: {self.config.RF_MAX}")
            return True
        if k == 'down' and not m & pygame.KMOD_SHIFT:
            self.config.RF_MAX -= 10
            print(f"rf_max: {self.config.RF_MAX}")
            return True
        if k == 'up' and (m & pygame.KMOD_SHIFT):
            self.config.RF_MIN += 10
            print(f"rf_min: {self.config.RF_MIN}")
            return True
        if k == 'down' and (m & pygame.KMOD_SHIFT):
            self.config.RF_MIN -= 10
            print(f"rf_min: {self.config.RF_MIN}")
            return True
        return False
