import 'package:flutter/material.dart';

/// Recitation recording screen.
/// Student selects surah/ayah range, records audio, and uploads for AI analysis.
class RecordScreen extends StatefulWidget {
  const RecordScreen({super.key});

  @override
  State<RecordScreen> createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> {
  bool _isRecording = false;
  int _selectedSurah = 1;
  int _ayahStart = 1;
  int _ayahEnd = 7;
  String _recitationType = 'new_lesson';
  Duration _recordingDuration = Duration.zero;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Record Recitation',
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    )),
            const SizedBox(height: 24),

            // Surah/Ayah Selection
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('What are you reciting?',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 16),
                    // Recitation type
                    SegmentedButton<String>(
                      segments: const [
                        ButtonSegment(value: 'new_lesson', label: Text('New')),
                        ButtonSegment(value: 'revision', label: Text('Revision')),
                        ButtonSegment(value: 'test', label: Text('Test')),
                      ],
                      selected: {_recitationType},
                      onSelectionChanged: (v) =>
                          setState(() => _recitationType = v.first),
                    ),
                    const SizedBox(height: 16),
                    // Surah picker
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButtonFormField<int>(
                            value: _selectedSurah,
                            decoration: const InputDecoration(
                              labelText: 'Surah',
                              border: OutlineInputBorder(),
                            ),
                            items: List.generate(
                              114,
                              (i) => DropdownMenuItem(
                                value: i + 1,
                                child: Text('${i + 1}'),
                              ),
                            ),
                            onChanged: (v) =>
                                setState(() => _selectedSurah = v ?? 1),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            decoration: const InputDecoration(
                              labelText: 'Ayah Start',
                              border: OutlineInputBorder(),
                            ),
                            keyboardType: TextInputType.number,
                            initialValue: '$_ayahStart',
                            onChanged: (v) => setState(
                                () => _ayahStart = int.tryParse(v) ?? 1),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            decoration: const InputDecoration(
                              labelText: 'Ayah End',
                              border: OutlineInputBorder(),
                            ),
                            keyboardType: TextInputType.number,
                            initialValue: '$_ayahEnd',
                            onChanged: (v) => setState(
                                () => _ayahEnd = int.tryParse(v) ?? 7),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Recording Controls
            Center(
              child: Column(
                children: [
                  // Timer
                  Text(
                    _formatDuration(_recordingDuration),
                    style: Theme.of(context).textTheme.displayMedium?.copyWith(
                          fontFamily: 'monospace',
                          fontWeight: FontWeight.w300,
                        ),
                  ),
                  const SizedBox(height: 24),
                  // Record button
                  GestureDetector(
                    onTap: _toggleRecording,
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _isRecording
                            ? Colors.red
                            : Theme.of(context).colorScheme.primary,
                      ),
                      child: Icon(
                        _isRecording ? Icons.stop : Icons.mic,
                        color: Colors.white,
                        size: 36,
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    _isRecording ? 'Tap to stop' : 'Tap to record',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _toggleRecording() {
    setState(() => _isRecording = !_isRecording);
    // In full implementation:
    // - Use `record` package to capture audio
    // - Stream duration updates
    // - On stop, upload via API client
  }

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }
}
