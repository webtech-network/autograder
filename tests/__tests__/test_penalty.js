const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');

const axiosNoRedirect = axios.create({
    maxRedirects: 0,
    validateStatus: function (status) {
        return status >= 200 && status < 500;
    }
});


function expectContentType(response, expectedType) {
    const contentType = response.headers['content-type'];
    expect(contentType).toBeDefined();
    expect(contentType).toMatch(new RegExp(expectedType));
}

function expectFormFields($, expectedFieldNames) {
    expectedFieldNames.forEach(fieldName => {
        const field = $(`[name="${fieldName}"]`);
        expect(field.length).toBeGreaterThan(0);
    });
}

describe('Penalty Tests', () => {

    const contactSubmission = {
        nome: "Chaerin Kim",
        email: "chaerin@gmail.com",
        assunto: "Reclamação",
        mensagem: "O lanche estava frio e nojento!"
    };

    describe('1. Incorrect HTTP Methods', () => {

        async function testUnexpectedMethod(path, method, expectedStatus = [404, 405]) {
            let response;
            try {
                response = await axiosNoRedirect({
                    method: method,
                    url: `${BASE_URL}${path}`,
                    data: method === 'POST' || method === 'PUT' ? { test: 'data' } : undefined,
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    validateStatus: function (status) {
                        return true; 
                    }
                });
            } catch (error) {
                response = error.response;
                if (!response) {
                    throw new Error(`Network error or connection refused for ${method} ${path}: ${error.message}`);
                }
            }
            expect(expectedStatus).toContain(response.status);
        }

        test('GET / should not accept POST', async () => await testUnexpectedMethod('/', 'POST'));
        test('GET / should not accept PUT', async () => await testUnexpectedMethod('/', 'PUT'));
        test('GET / should not accept DELETE', async () => await testUnexpectedMethod('/', 'DELETE'));
        test('GET / should not accept PATCH', async () => await testUnexpectedMethod('/', 'PATCH'));

        test('GET /sugestao should not accept POST', async () => await testUnexpectedMethod('/sugestao', 'POST'));
        test('GET /sugestao should not accept PUT', async () => await testUnexpectedMethod('/sugestao', 'PUT'));
        test('GET /sugestao should not accept DELETE', async () => await testUnexpectedMethod('/sugestao', 'DELETE'));
        test('GET /sugestao should not accept PATCH', async () => await testUnexpectedMethod('/sugestao', 'PATCH'));


        test('GET /contato should not accept PUT', async () => await testUnexpectedMethod('/contato', 'PUT'));
        test('GET /contato should not accept DELETE', async () => await testUnexpectedMethod('/contato', 'DELETE'));
        test('GET /contato should not accept DELETE', async () => await testUnexpectedMethod('/contato', 'PATCH'));


        test('GET /api/lanches should not accept POST', async () => await testUnexpectedMethod('/api/lanches', 'POST'));
        test('GET /api/lanches should not accept PUT', async () => await testUnexpectedMethod('/api/lanches', 'PUT'));
        test('GET /api/lanches should not accept DELETE', async () => await testUnexpectedMethod('/api/lanches', 'DELETE'));
        test('GET /api/lanches should not accept PATCH', async () => await testUnexpectedMethod('/api/lanches', 'PATCH'));

        describe('Conditional: /contato-recebido (if PRG is used)', () => {
            let initialPostResponse; 
            let isPrgUsed = false;

            beforeAll(async () => {
                try {
                    initialPostResponse = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, {
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        validateStatus: status => true
                    });
                    if (initialPostResponse.status >= 300 && initialPostResponse.status < 400 && initialPostResponse.headers.location === '/contato-recebido') {
                        isPrgUsed = true;
                    }
                } catch (error) {
                    if (error.response && error.response.status >= 300 && error.response.status < 400 && error.response.headers.location === '/contato-recebido') {
                        isPrgUsed = true;
                    }
                }
            });

            beforeEach(() => {
                if (!isPrgUsed) {
                    pending('Skipping /contato-recebido method tests as PRG pattern was not detected for POST /contato.');
                }
            });

            test('/contato-recebido should not accept POST', async () => await testUnexpectedMethod('/contato-recebido', 'POST'));
            test('/contato-recebido should not accept PUT', async () => await testUnexpectedMethod('/contato-recebido', 'PUT'));
            test('/contato-recebido should not accept DELETE', async () => await testUnexpectedMethod('/contato-recebido', 'DELETE'));
        });
    });

    describe('2. Incorrect Content-Type Returns', () => {

        test('GET / should return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            expectContentType(response, 'text/html');
        });

        test('GET /sugestao should return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/sugestao?nome=test&ingredientes=test`);
            expectContentType(response, 'text/html');
        });

        test('GET /contato should return text/html', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            expectContentType(response, 'text/html');
        });

        test('GET /api/lanches should return application/json', async () => {
            const response = await axios.get(`${BASE_URL}/api/lanches`);
            expectContentType(response, 'application/json');
        });

        test('Static CSS file should return text/css', async () => {
            const response = await axios.get(`${BASE_URL}/css/style.css`);
            expectContentType(response, 'text/css');
        });

        // Test for POST /contato's final HTML response content type
        test('POST /contato final response should be text/html (adaptive)', async () => {
            let finalResponse;
            try {
                const initialResponse = await axiosNoRedirect.post(`${BASE_URL}/contato`, contactSubmission, {
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    validateStatus: status => true
                });

                if (initialResponse.status >= 300 && initialResponse.status < 400) {
                    finalResponse = await axios.get(`${BASE_URL}${initialResponse.headers.location}`);
                } else {
                    finalResponse = initialResponse;
                }
            } catch (error) {
                // Handle errors like connection refused or Axios throwing for 3xx
                if (error.response && error.response.status >= 300 && error.response.status < 400) {
                     finalResponse = await axios.get(`${BASE_URL}${error.response.headers.location}`);
                } else {
                    throw error; // Re-throw other errors
                }
            }
            expectContentType(finalResponse, 'text/html');
        });
    });

    describe('3. Incorrect Form Field Name Attributes', () => {

        test('index.html form should have correct name attributes', async () => {
            const response = await axios.get(`${BASE_URL}/`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'ingredientes']);
        });

        test('contato.html form should have correct name attributes', async () => {
            const response = await axios.get(`${BASE_URL}/contato`);
            const $ = cheerio.load(response.data);
            expectFormFields($, ['nome', 'email', 'assunto', 'mensagem']);
        });
    });
});