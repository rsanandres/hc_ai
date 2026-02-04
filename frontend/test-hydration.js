
const puppeteer = require('puppeteer');

(async () => {
    // Launch new browser instance
    const browser = await puppeteer.launch({
        args: ['--no-sandbox', '--disable-setuid-sandbox'], // Required for some CI/container environments
    });
    const page = await browser.newPage();

    const errors = [];

    // Listen for console events
    page.on('console', msg => {
        if (msg.type() === 'error') {
            errors.push(msg.text());
        }
    });

    // Also listen for page crashes or error events
    page.on('pageerror', err => {
        errors.push(err.toString());
    });

    try {
        // Navigate to localhost
        await page.goto('http://localhost:3000', { waitUntil: 'networkidle0' });

        // Wait a bit to ensure hydration logic runs
        await new Promise(r => setTimeout(r, 2000));

        // Check for specific hydration errors in captured logs
        const hydrationErrors = errors.filter(e =>
            e.toLowerCase().includes('hydration') ||
            e.toLowerCase().includes('react') ||
            e.toLowerCase().includes('mismatch')
        );

        if (hydrationErrors.length > 0) {
            console.error('❌ Hydration errors found:');
            hydrationErrors.forEach(e => console.error(`- ${e}`));
            process.exit(1);
        } else {
            console.log('✅ No hydration errors detected.');
        }

    } catch (err) {
        console.error('❌ Test failed to run:', err);
        process.exit(1);
    } finally {
        await browser.close();
    }
})();
