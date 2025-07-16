function safeTest(description, asyncTestFn) {
    test(description, async () => {
        try {
            await asyncTestFn();
        } catch (error) {
            if (error.code === 'ECONNREFUSED') {
                throw new Error(`Connection refused on test: "${description}". Is the server running?`);
            }
            throw new Error(`An unexpected error occurred in test "${description}": ${error.message}`);
        }
    });
}

global.safeTest = safeTest;