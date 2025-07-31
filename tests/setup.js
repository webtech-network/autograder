function safeTest(description, asyncTestFn) {
    test(description, async () => {
        try {
            await asyncTestFn();
        } catch (error) {
            if (error.code === 'ECONNREFUSED') {
                throw new Error(`Connection refused on test: "${description}". Is the server running?`);
            } else if (error.code === 'ECONNABORTED'){
                throw new Error(`There was a timeout on test: "${description}". Test it locally and try again`)
            }
            throw new Error(`An unexpected error occurred in test "${description}": ${error.message}`);
        }
    });
}

global.safeTest = safeTest;