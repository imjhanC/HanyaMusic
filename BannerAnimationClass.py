import customtkinter as ctk
import math
import random
from datetime import datetime
import colorsys

class AnimatedBanner(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        
        # Animation variables
        self.animation_offset = 0
        self.animation_speed = 1.2  # Reduced speed for better performance
        self.canvas_width = 800
        self.canvas_height = 200
        
        # Enhanced wave animation variables
        self.wave_start_points = []
        self.particle_effects = []
        self.color_shift_offset = 0
        self.breathing_offset = 0
        self.generate_wave_start_points()
        self.generate_particles()
        
        # Performance optimization flags
        self.is_visible = True
        self.animation_active = True
        
        # Create canvas for gradient animation
        self.canvas = ctk.CTkCanvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            highlightthickness=0,
            bg="#000000"
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Create text label overlay with shadow effect
        self.text_shadow = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="gray20"  # Dark gray shadow
        )
        self.text_shadow.place(relx=0.502, rely=0.502, anchor="center")
        
        self.text_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color="white"
        )
        self.text_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Get initial greeting and colors
        self.update_greeting()
        
        # Start animation
        self.animate_banner()
        
        # Bind resize event
        self.canvas.bind('<Configure>', self.on_canvas_resize)
    
    def generate_wave_start_points(self):
        """Generate random wave start points for dynamic animation"""
        self.wave_start_points = []
        for i in range(5):  # Reduced from 7 to 5 for better performance
            self.wave_start_points.append({
                'x': random.uniform(0, self.canvas_width),
                'y': random.uniform(0, self.canvas_height),
                'speed': random.uniform(0.2, 1.0),  # Reduced speed range
                'amplitude': random.uniform(15, 40),  # Reduced amplitude
                'frequency': random.uniform(0.002, 0.008),  # Reduced frequency
                'phase': random.uniform(0, 2 * math.pi),
                'direction': random.choice([-1, 1])
            })
    
    def generate_particles(self):
        """Generate floating particles for extra visual appeal"""
        self.particle_effects = []
        for i in range(8):  # Reduced from 15 to 8 for better performance
            self.particle_effects.append({
                'x': random.uniform(0, self.canvas_width),
                'y': random.uniform(0, self.canvas_height),
                'speed_x': random.uniform(-0.3, 0.3),  # Reduced speed
                'speed_y': random.uniform(-0.2, 0.2),  # Reduced speed
                'size': random.uniform(2, 4),  # Reduced size
                'opacity': random.uniform(0.1, 0.3),  # Reduced opacity
                'pulse_speed': random.uniform(0.01, 0.03)  # Reduced pulse speed
            })
    
    def get_time_based_greeting_and_colors(self):
        """Get greeting message and enhanced color scheme based on current time"""
        current_hour = datetime.now().hour
 
        if 5 <= current_hour < 12:
            # Morning - Warm sunrise colors
            greeting = "Good Morning! 🌅"
            colors = [
                "#FF6B35", "#F7931E", "#FFD23F", "#FFF700", 
                "#CDDC39", "#8BC34A", "#4CAF50", "#009688",
                "#00BCD4", "#03A9F4", "#2196F3", "#FF5722"
            ]
 
        elif 12 <= current_hour < 17:
            # Afternoon - Bright vibrant colors
            greeting = "Good Afternoon! ☀️"
            colors = [
                "#E91E63", "#F44336", "#FF5722", "#FF9800",
                "#FFC107", "#FFEB3B", "#CDDC39", "#8BC34A",
                "#4CAF50", "#009688", "#00BCD4", "#2196F3"
            ]
 
        elif 17 <= current_hour < 21:
            # Evening - Sunset colors
            greeting = "Good Evening! 🌇"
            colors = [
                "#FF5722", "#E91E63", "#9C27B0", "#673AB7",
                "#3F51B5", "#2196F3", "#03A9F4", "#00BCD4",
                "#009688", "#4CAF50", "#8BC34A", "#FF9800"
            ]
 
        else:
            # Night - Deep, mystical colors
            greeting = "Good Night! 🌙"
            colors = [
                "#1A237E", "#283593", "#303F9F", "#3F51B5",
                "#512DA8", "#673AB7", "#7B1FA2", "#8E24AA",
                "#9C27B0", "#AD1457", "#C2185B", "#E91E63"
            ]
 
        return greeting, colors
    
    def update_greeting(self):
        """Update greeting text and colors"""
        greeting, self.colors = self.get_time_based_greeting_and_colors()
        self.text_label.configure(text=greeting)
        self.text_shadow.configure(text=greeting)
    
    def on_canvas_resize(self, event):
        """Handle canvas resize"""
        self.canvas_width = event.width
        self.canvas_height = event.height
        # Regenerate particles for new canvas size
        self.generate_particles()
    
    def perlin_noise_1d(self, x, scale=0.05):  # Reduced scale for performance
        """Simple 1D Perlin-like noise for smooth variations"""
        x = x * scale
        i = int(x)
        f = x - i
        # Smooth interpolation
        u = f * f * f * (f * (f * 6 - 15) + 10)
        return math.sin(i * 12.9898) * (1 - u) + math.sin((i + 1) * 12.9898) * u
    
    def hsv_to_hex(self, h, s, v):
        """Convert HSV to hex color"""
        rgb = colorsys.hsv_to_rgb(h, s, v)
        return f"#{int(rgb[0]*255):02x}{int(rgb[1]*255):02x}{int(rgb[2]*255):02x}"
    
    def create_ultra_smooth_gradient_wave(self, x_offset):
        """Create ultra-smooth gradient wave animation with enhanced blending"""
        self.canvas.delete("gradient")
        self.canvas.delete("particles")
        
        # Reduced resolution for better performance
        strips = 600  # Reduced from 1200 to 600
        strip_width = self.canvas_width / strips
        
        # Calculate breathing effect for subtle color intensity changes
        self.breathing_offset += 0.005  # Reduced from 0.01
        breathing_intensity = (math.sin(self.breathing_offset) + 1) * 0.5
        
        # Color shift for dynamic palette rotation
        self.color_shift_offset += 0.001  # Reduced from 0.002
        
        for i in range(-50, strips + 50):  # Reduced extra strips
            x = (i * strip_width) + x_offset
            
            # Simplified wave calculation for better performance
            total_wave_offset = 0
            for j, wave_point in enumerate(self.wave_start_points):
                # Update wave point position dynamically
                wave_point['x'] += wave_point['speed'] * wave_point['direction'] * 0.05  # Reduced from 0.1
                if wave_point['x'] < 0 or wave_point['x'] > self.canvas_width:
                    wave_point['direction'] *= -1
                
                distance_from_wave = abs(x - wave_point['x'])
                
                # Simplified wave calculation
                primary_wave = math.sin(
                    (distance_from_wave + self.animation_offset * wave_point['speed']) * 
                    wave_point['frequency'] + wave_point['phase']
                ) * wave_point['amplitude']
                
                # Removed secondary wave and noise for performance
                combined_wave = primary_wave
                
                # Simplified fade function
                fade_factor = max(0, 1 - (distance_from_wave / 200))
                total_wave_offset += combined_wave * fade_factor
            
            # Normalize wave offset
            wave_offset = total_wave_offset / len(self.wave_start_points)
            
            # Enhanced color progression with multiple techniques
            base_progress = ((i + self.animation_offset * 0.005) / strips) % 1.0  # Reduced from 0.008
            
            # Add wave influence to color progression for dynamic shifts
            wave_influence = wave_offset * 0.0005  # Reduced from 0.001
            color_progress = (base_progress + wave_influence + self.color_shift_offset) % 1.0
            
            # Multi-color interpolation for ultra-smooth transitions
            total_colors = len(self.colors)
            exact_color_pos = color_progress * total_colors
            color_index = int(exact_color_pos) % total_colors
            next_color_index = (color_index + 1) % total_colors
            next_next_color_index = (color_index + 2) % total_colors
            
            # Get three colors for cubic interpolation
            color1 = self.colors[color_index]
            color2 = self.colors[next_color_index]
            color3 = self.colors[next_next_color_index]
            
            # Cubic interpolation factor
            t = exact_color_pos % 1.0
            
            # Triple-color blending for ultimate smoothness
            if t < 0.5:
                # Blend between color1 and color2
                blend_t = t * 2
                interpolated_color = self.advanced_color_blend(color1, color2, blend_t, breathing_intensity)
            else:
                # Blend between color2 and color3
                blend_t = (t - 0.5) * 2
                interpolated_color = self.advanced_color_blend(color2, color3, blend_t, breathing_intensity)
            
            # Create gradient strip with wave offset
            y1 = -20  # Reduced from -30
            y2 = self.canvas_height + wave_offset + 20  # Reduced from +30
            
            # Only draw visible strips
            if x > -strip_width * 2 and x < self.canvas_width + strip_width * 2:
                self.canvas.create_rectangle(
                    x, y1, x + strip_width + 1, y2,  # +1 to prevent gaps
                    fill=interpolated_color,
                    outline="",
                    tags="gradient"
                )
        
        # Add floating particles (simplified)
        if self.animation_active:
            self.draw_particles()
    
    def advanced_color_blend(self, color1, color2, t, intensity_mod=1.0):
        """Advanced color blending with HSV interpolation and intensity modulation"""
        # Convert to RGB
        c1_rgb = self.hex_to_rgb(color1)
        c2_rgb = self.hex_to_rgb(color2)
        
        # Convert to HSV for better color blending
        c1_hsv = colorsys.rgb_to_hsv(c1_rgb[0]/255, c1_rgb[1]/255, c1_rgb[2]/255)
        c2_hsv = colorsys.rgb_to_hsv(c2_rgb[0]/255, c2_rgb[1]/255, c2_rgb[2]/255)
        
        # Ultra-smooth easing
        t = self.ultra_smooth_ease_v2(t)
        
        # Handle hue wraparound for smooth transitions
        h1, h2 = c1_hsv[0], c2_hsv[0]
        if abs(h2 - h1) > 0.5:
            if h1 > h2:
                h2 += 1.0
            else:
                h1 += 1.0
        
        # Interpolate in HSV space
        h = (h1 + (h2 - h1) * t) % 1.0
        s = c1_hsv[1] + (c2_hsv[1] - c1_hsv[1]) * t
        v = (c1_hsv[2] + (c2_hsv[2] - c1_hsv[2]) * t) * intensity_mod
        
        # Ensure values are in valid range
        s = max(0, min(1, s))
        v = max(0, min(1, v))
        
        return self.hsv_to_hex(h, s, v)
    
    def draw_particles(self):
        """Draw floating particles for extra visual appeal"""
        for particle in self.particle_effects:
            # Update particle position
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            
            # Wrap around screen
            if particle['x'] < 0:
                particle['x'] = self.canvas_width
            elif particle['x'] > self.canvas_width:
                particle['x'] = 0
            
            if particle['y'] < 0:
                particle['y'] = self.canvas_height
            elif particle['y'] > self.canvas_height:
                particle['y'] = 0
            
            # Pulsing opacity
            pulse = (math.sin(self.animation_offset * particle['pulse_speed']) + 1) * 0.5
            current_opacity = particle['opacity'] * pulse
            
            # Create particle color based on current gradient - FIXED INDEX ERROR
            color_index = int((particle['x'] / self.canvas_width) * len(self.colors))
            color_index = max(0, min(len(self.colors) - 1, color_index))  # Ensure valid index
            particle_color = self.colors[color_index]
            
            # Draw particle
            self.canvas.create_oval(
                particle['x'] - particle['size'], particle['y'] - particle['size'],
                particle['x'] + particle['size'], particle['y'] + particle['size'],
                fill=particle_color, outline="",
                tags="particles"
            )
    
    def ultra_smooth_ease_v2(self, t):
        """Enhanced ultra-smooth easing function"""
        t = max(0, min(1, t))
        # Combination of multiple easing functions for ultimate smoothness
        ease1 = t * t * t * (t * (t * 6 - 15) + 10)
        ease2 = 1 - pow(1 - t, 4)
        ease3 = t * t * (3 - 2 * t)
        return (ease1 * 0.5 + ease2 * 0.3 + ease3 * 0.2)
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB tuple"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def animate_banner(self):
        """Animate the gradient banner with enhanced features"""
        if not self.winfo_exists() or not self.animation_active:
            return
        
        # Update animation offset
        self.animation_offset += self.animation_speed
        
        # Regenerate wave points occasionally for variety
        if self.animation_offset % 600 == 0:  # Increased from 400
            self.generate_wave_start_points()
        
        # Add some particles occasionally
        if self.animation_offset % 300 == 0 and len(self.particle_effects) < 12:  # Reduced from 200 and 20
            self.particle_effects.append({
                'x': random.uniform(0, self.canvas_width),
                'y': random.uniform(0, self.canvas_height),
                'speed_x': random.uniform(-0.3, 0.3),
                'speed_y': random.uniform(-0.2, 0.2),
                'size': random.uniform(2, 4),
                'opacity': random.uniform(0.1, 0.3),
                'pulse_speed': random.uniform(0.01, 0.03)
            })
        
        # Create smooth animated gradient with multiple wave influences
        primary_wave = math.sin(self.animation_offset * 0.01) * 20  # Reduced from 0.015 and 30
        secondary_wave = math.cos(self.animation_offset * 0.02) * 15  # Reduced from 0.025 and 20
        wave_offset = primary_wave + secondary_wave
        
        self.create_ultra_smooth_gradient_wave(wave_offset)
        
        # Update greeting periodically
        if self.animation_offset % 2400 == 0:  # Increased from 1800
            self.update_greeting()
        
        # Smooth 60 FPS animation
        self.after(20, self.animate_banner)  # Increased from 16ms to 20ms for better performance