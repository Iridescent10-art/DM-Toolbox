using System;
using System.IO;
using System.Diagnostics;
using System.Windows.Forms;

namespace DMBOX
{
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            try
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string runtimePyw = Path.Combine(baseDir, "runtime", "pythonw.exe");
                string pyExe = File.Exists(runtimePyw) ? runtimePyw : "pythonw.exe";
                string scriptPath = Path.Combine(baseDir, "launcher", "main.py");

                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show("未在程序目录下找到主启动文件:\n" + scriptPath, "DM工具箱 - 启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pyExe;
                psi.Arguments = "-B \"" + scriptPath + "\"";
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;

                Process.Start(psi);
            }
            catch (Exception ex)
            {
                MessageBox.Show("启动 DM工具箱 出现异常:\n" + ex.Message, "DM工具箱", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }
}
