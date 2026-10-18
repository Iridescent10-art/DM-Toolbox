using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Security.Principal;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Win32;

namespace DlssIndicatorSwitch
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new SwitchForm());
        }
    }

    public sealed class SwitchForm : Form
    {
        private const string KeyPath = @"SOFTWARE\NVIDIA Corporation\Global\NGXCore";
        private const string ValueName = "ShowDlssIndicator";
        private const uint IndicatorOn = 0x00000400;

        private readonly Panel topBar;
        private readonly PictureBox appIcon;
        private readonly Label titleLabel;
        private readonly Label subtitleLabel;
        private readonly Button minimizeButton;
        private readonly Button closeButton;
        private readonly Panel stateCard;
        private readonly Label stateCaptionLabel;
        private readonly Label stateValueLabel;
        private readonly Label stateDescriptionLabel;
        private readonly Button toggleButton;
        private readonly Button refreshButton;
        private readonly Panel footerPanel;
        private readonly Label footerLabel;
        private readonly Timer revealTimer;
        private readonly Bitmap iconBitmap;
        private bool isOn;
        private bool isAdmin;

        public SwitchForm()
        {
            Text = "DLSS 超分显示开关";
            Name = "DlssIndicatorSwitchForm";
            ClientSize = new Size(560, 380);
            MinimumSize = new Size(560, 380);
            MaximumSize = new Size(560, 380);
            FormBorderStyle = FormBorderStyle.None;
            MaximizeBox = false;
            MinimizeBox = true;
            ShowIcon = false;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = Color.FromArgb(28, 31, 36);
            Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Regular, GraphicsUnit.Point);
            AutoScaleMode = AutoScaleMode.Dpi;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                ControlStyles.OptimizedDoubleBuffer, true);

            try
            {
                Icon associatedIcon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
                if (associatedIcon != null)
                {
                    Icon = associatedIcon;
                    iconBitmap = associatedIcon.ToBitmap();
                }
            }
            catch
            {
            }

            topBar = new Panel();
            topBar.SetBounds(0, 0, 560, 72);
            topBar.BackColor = Color.FromArgb(35, 38, 43);
            topBar.MouseMove += DragWindow;
            topBar.MouseDown += DragWindow;

            appIcon = new PictureBox();
            appIcon.SetBounds(20, 18, 36, 36);
            appIcon.BackColor = Color.Transparent;
            appIcon.SizeMode = PictureBoxSizeMode.Zoom;
            appIcon.Image = iconBitmap;
            appIcon.MouseMove += DragWindow;
            appIcon.MouseDown += DragWindow;

            titleLabel = new Label();
            titleLabel.Text = "DLSS 超分显示开关";
            titleLabel.Font = new Font("Microsoft YaHei UI", 12F, FontStyle.Bold, GraphicsUnit.Point);
            titleLabel.ForeColor = Color.White;
            titleLabel.BackColor = Color.Transparent;
            titleLabel.AutoSize = true;
            titleLabel.Location = new Point(68, 14);
            titleLabel.MouseMove += DragWindow;
            titleLabel.MouseDown += DragWindow;

            subtitleLabel = new Label();
            subtitleLabel.Text = "NVIDIA 超分状态指示器";
            subtitleLabel.Font = new Font("Microsoft YaHei UI", 8.5F, FontStyle.Regular, GraphicsUnit.Point);
            subtitleLabel.ForeColor = Color.FromArgb(166, 174, 184);
            subtitleLabel.BackColor = Color.Transparent;
            subtitleLabel.AutoSize = true;
            subtitleLabel.Location = new Point(69, 41);
            subtitleLabel.MouseMove += DragWindow;
            subtitleLabel.MouseDown += DragWindow;

            minimizeButton = new TitleBarButton();
            minimizeButton.SetBounds(456, 0, 52, 72);
            minimizeButton.Text = "—";
            minimizeButton.ForeColor = Color.FromArgb(186, 193, 201);
            minimizeButton.BackColor = topBar.BackColor;
            minimizeButton.TabStop = false;
            minimizeButton.Click += delegate { WindowState = FormWindowState.Minimized; };

            closeButton = new TitleBarButton();
            closeButton.SetBounds(508, 0, 52, 72);
            closeButton.Text = "×";
            closeButton.ForeColor = Color.FromArgb(186, 193, 201);
            closeButton.BackColor = topBar.BackColor;
            closeButton.TabStop = false;
            closeButton.Click += delegate { Close(); };

            topBar.Controls.Add(appIcon);
            topBar.Controls.Add(titleLabel);
            topBar.Controls.Add(subtitleLabel);
            topBar.Controls.Add(minimizeButton);
            topBar.Controls.Add(closeButton);

            stateCard = new Panel();
            stateCard.SetBounds(20, 92, 520, 126);
            stateCard.BackColor = BackColor;
            stateCard.Paint += PaintStateCard;

            stateCaptionLabel = new Label();
            stateCaptionLabel.Text = "当前状态";
            stateCaptionLabel.Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Regular, GraphicsUnit.Point);
            stateCaptionLabel.ForeColor = Color.FromArgb(167, 175, 185);
            stateCaptionLabel.BackColor = Color.Transparent;
            stateCaptionLabel.AutoSize = true;
            stateCaptionLabel.Location = new Point(22, 18);

            stateValueLabel = new Label();
            stateValueLabel.Font = new Font("Microsoft YaHei UI", 22F, FontStyle.Bold, GraphicsUnit.Pixel);
            stateValueLabel.ForeColor = Color.White;
            stateValueLabel.BackColor = Color.Transparent;
            stateValueLabel.AutoSize = true;
            stateValueLabel.Location = new Point(20, 45);

            stateDescriptionLabel = new Label();
            stateDescriptionLabel.Text = "修改后请重新启动游戏以查看效果";
            stateDescriptionLabel.Font = new Font("Microsoft YaHei UI", 8.5F, FontStyle.Regular, GraphicsUnit.Point);
            stateDescriptionLabel.ForeColor = Color.FromArgb(156, 165, 175);
            stateDescriptionLabel.BackColor = Color.Transparent;
            stateDescriptionLabel.AutoSize = true;
            stateDescriptionLabel.Location = new Point(22, 94);

            stateCard.Controls.Add(stateCaptionLabel);
            stateCard.Controls.Add(stateValueLabel);
            stateCard.Controls.Add(stateDescriptionLabel);

            toggleButton = new RoundedButton();
            toggleButton.SetBounds(20, 238, 320, 58);
            toggleButton.FlatStyle = FlatStyle.Flat;
            toggleButton.FlatAppearance.BorderSize = 0;
            toggleButton.UseVisualStyleBackColor = false;
            toggleButton.Cursor = Cursors.Hand;
            toggleButton.Font = new Font("Microsoft YaHei UI", 11F, FontStyle.Bold, GraphicsUnit.Point);
            toggleButton.ForeColor = Color.White;
            toggleButton.BackColor = Color.FromArgb(76, 173, 80);
            toggleButton.Text = "打开超分显示";
            toggleButton.TabStop = false;
            toggleButton.Click += ToggleButtonClick;

            refreshButton = new RoundedButton();
            refreshButton.SetBounds(354, 238, 186, 58);
            refreshButton.FlatStyle = FlatStyle.Flat;
            refreshButton.FlatAppearance.BorderSize = 0;
            refreshButton.UseVisualStyleBackColor = false;
            refreshButton.Cursor = Cursors.Hand;
            refreshButton.Font = new Font("Microsoft YaHei UI", 9F, FontStyle.Regular, GraphicsUnit.Point);
            refreshButton.ForeColor = Color.FromArgb(216, 222, 228);
            refreshButton.BackColor = Color.FromArgb(61, 67, 73);
            refreshButton.Text = "刷新状态";
            refreshButton.TabStop = false;
            refreshButton.Click += delegate { LoadState(true); };

            footerPanel = new Panel();
            footerPanel.SetBounds(20, 318, 520, 42);
            footerPanel.BackColor = BackColor;
            footerPanel.Paint += PaintFooter;

            footerLabel = new Label();
            footerLabel.Text = "注册表路径：HKLM\\SOFTWARE\\NVIDIA Corporation\\Global\\NGXCore";
            footerLabel.Font = new Font("Microsoft YaHei UI", 8F, FontStyle.Regular, GraphicsUnit.Point);
            footerLabel.ForeColor = Color.FromArgb(151, 159, 169);
            footerLabel.BackColor = Color.Transparent;
            footerLabel.AutoSize = true;
            footerLabel.Location = new Point(17, 13);

            footerPanel.Controls.Add(footerLabel);

            Controls.Add(stateCard);
            Controls.Add(toggleButton);
            Controls.Add(refreshButton);
            Controls.Add(footerPanel);
            Controls.Add(topBar);

            ApplyRoundedWindow();

            revealTimer = new Timer();
            revealTimer.Interval = 80;
            revealTimer.Tick += RevealTick;
            revealTimer.Start();

            Load += delegate { LoadState(false); };
        }

        private void PaintStateCard(object sender, PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            e.Graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;

            Rectangle bounds = new Rectangle(0, 0, stateCard.Width - 1, stateCard.Height - 1);
            using (GraphicsPath path = RoundedRectangle(bounds, 18))
            using (SolidBrush fill = new SolidBrush(Color.FromArgb(45, 50, 56)))
            using (Pen border = new Pen(Color.FromArgb(68, 74, 81), 1F))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(border, path);
            }

            int indicatorX = stateCard.Width - 92;
            Rectangle trackBounds = new Rectangle(indicatorX, 36, 64, 32);
            using (GraphicsPath trackPath = RoundedRectangle(trackBounds, 16))
            using (SolidBrush trackBrush = new SolidBrush(isOn ? Color.FromArgb(76, 173, 80) : Color.FromArgb(105, 113, 121)))
            {
                e.Graphics.FillPath(trackBrush, trackPath);
            }

            Rectangle knob = new Rectangle(isOn ? indicatorX + 35 : indicatorX + 4, 40, 24, 24);
            e.Graphics.FillEllipse(Brushes.White, knob);
        }

        private void PaintFooter(object sender, PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle bounds = new Rectangle(0, 0, footerPanel.Width - 1, footerPanel.Height - 1);
            using (GraphicsPath path = RoundedRectangle(bounds, 13))
            using (SolidBrush fill = new SolidBrush(Color.FromArgb(39, 43, 48)))
            using (Pen border = new Pen(Color.FromArgb(62, 68, 75), 1F))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(border, path);
            }

            e.Graphics.FillEllipse(new SolidBrush(Color.FromArgb(76, 173, 80)),
                new Rectangle(10, 18, 6, 6));
        }

        private static GraphicsPath RoundedRectangle(Rectangle bounds, int radius)
        {
            int diameter = radius * 2;
            GraphicsPath path = new GraphicsPath();
            path.AddArc(bounds.X, bounds.Y, diameter, diameter, 180, 90);
            path.AddArc(bounds.Right - diameter, bounds.Y, diameter, diameter, 270, 90);
            path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(bounds.X, bounds.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            return path;
        }

        private void LoadState(bool showErrors)
        {
            try
            {
                isAdmin = IsRunAsAdministrator();

                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(KeyPath, false))
                {
                    object raw = key == null ? null : key.GetValue(ValueName, null);
                    isOn = raw is int && unchecked((uint)(int)raw) == IndicatorOn;
                }

                UpdateStateUi();

                if (!isAdmin)
                {
                    stateDescriptionLabel.Text = "需要管理员权限才能修改";
                    toggleButton.Enabled = false;
                    toggleButton.BackColor = Color.FromArgb(75, 81, 88);
                    toggleButton.Text = "需要管理员权限";
                }
            }
            catch (Exception ex)
            {
                if (showErrors)
                {
                    MessageBox.Show(this, "读取当前状态失败：\r\n\r\n" + ex.Message,
                        Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }

        private void UpdateStateUi()
        {
            stateValueLabel.Text = isOn ? "已打开" : "已关闭";
            stateValueLabel.ForeColor = Color.White;
            stateCaptionLabel.Text = isOn ? "当前状态 · 指示器开启" : "当前状态 · 指示器关闭";
            stateDescriptionLabel.Text = "修改后请重新启动游戏以查看效果";

            if (isAdmin)
            {
                toggleButton.Enabled = true;
                toggleButton.Text = isOn ? "关闭超分显示" : "打开超分显示";
                toggleButton.BackColor = isOn ? Color.FromArgb(198, 82, 82) : Color.FromArgb(76, 173, 80);
            }

            stateCard.Invalidate();
        }

        private void ToggleButtonClick(object sender, EventArgs e)
        {
            bool desired = !isOn;

            try
            {
                using (RegistryKey key = Registry.LocalMachine.CreateSubKey(KeyPath, true))
                {
                    if (key == null)
                    {
                        throw new InvalidOperationException("无法创建或打开注册表项。");
                    }

                    key.SetValue(ValueName, unchecked((int)(desired ? IndicatorOn : 0)),
                        RegistryValueKind.DWord);
                }

                isOn = desired;
                UpdateStateUi();

                MessageBox.Show(this,
                    desired
                        ? "超分显示已打开。\r\n\r\n如果游戏正在运行，请重新启动游戏后查看效果。"
                        : "超分显示已关闭。\r\n\r\n如果游戏正在运行，请重新启动游戏后生效。",
                    Text, MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                string message = ex is UnauthorizedAccessException
                    ? "没有写入注册表的权限。\r\n\r\n请右键单击程序，选择“以管理员身份运行”。"
                    : "修改失败：\r\n\r\n" + ex.Message;

                MessageBox.Show(this, message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void DragWindow(object sender, MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left)
            {
                return;
            }

            ReleaseCapture();
            SendMessage(Handle, 0x00A1, (IntPtr)2, IntPtr.Zero);
        }

        private static bool IsRunAsAdministrator()
        {
            try
            {
                using (WindowsIdentity identity = WindowsIdentity.GetCurrent())
                {
                    WindowsPrincipal principal = new WindowsPrincipal(identity);
                    return principal.IsInRole(WindowsBuiltInRole.Administrator);
                }
            }
            catch
            {
                return false;
            }
        }

        private void ApplyRoundedWindow()
        {
            try
            {
                int preference = 2;
                DwmSetWindowAttribute(Handle, 33, ref preference, sizeof(int));

                if (Environment.OSVersion.Version.Build < 22000)
                {
                    using (GraphicsPath path = RoundedRectangle(new Rectangle(0, 0, Width, Height), 18))
                    {
                        Region = new Region(path);
                    }
                }
            }
            catch
            {
            }
        }

        private void RevealTick(object sender, EventArgs e)
        {
            revealTimer.Stop();
            Invalidate(true);
            Update();
        }

        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            revealTimer.Dispose();
            if (iconBitmap != null)
            {
                iconBitmap.Dispose();
            }

            base.OnFormClosed(e);
        }

        [DllImport("user32.dll")]
        private static extern bool ReleaseCapture();

        [DllImport("user32.dll")]
        private static extern IntPtr SendMessage(IntPtr handle, int message,
            IntPtr wParam, IntPtr lParam);

        [DllImport("dwmapi.dll", PreserveSig = true)]
        private static extern int DwmSetWindowAttribute(IntPtr handle, int attribute,
            ref int value, int valueSize);
    }

    public sealed class RoundedButton : Button
    {
        public RoundedButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                ControlStyles.OptimizedDoubleBuffer, true);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle bounds = new Rectangle(0, 0, ClientSize.Width - 1, ClientSize.Height - 1);
            e.Graphics.Clear(Parent == null ? BackColor : Parent.BackColor);

            using (GraphicsPath path = ButtonPath(bounds, 18))
            using (SolidBrush back = new SolidBrush(BackColor))
            {
                e.Graphics.FillPath(back, path);

                if (FlatAppearance.BorderSize > 0)
                {
                    using (Pen border = new Pen(FlatAppearance.BorderColor, 1F))
                    {
                        e.Graphics.DrawPath(border, path);
                    }
                }
            }

            TextRenderer.DrawText(e.Graphics, Text, Font, bounds, ForeColor,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter |
                TextFormatFlags.NoPrefix);
        }

        private static GraphicsPath ButtonPath(Rectangle bounds, int radius)
        {
            int diameter = radius * 2;
            GraphicsPath path = new GraphicsPath();
            path.AddArc(bounds.X, bounds.Y, diameter, diameter, 180, 90);
            path.AddArc(bounds.Right - diameter, bounds.Y, diameter, diameter, 270, 90);
            path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(bounds.X, bounds.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    public sealed class TitleBarButton : Button
    {
        public TitleBarButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                ControlStyles.OptimizedDoubleBuffer, true);
            TabStop = false;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            e.Graphics.Clear(BackColor);
            TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, ForeColor,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter |
                TextFormatFlags.NoPrefix);
        }
    }
}
