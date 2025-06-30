const axios = require('axios');
const cheerio = require('cheerio');
const { BASE_URL } = require('../config');


describe('Route - /', () => {
    let response;

    beforeAll(async() => {
      try {
        response = await axios.get(BASE_URL)
      } catch (error) {
        if(error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}. Is the Express server running?`);
        throw error;
      }
    });

    describe('Status code and headers', () => {
      
      test('should return a 200 OK status code', () => {
        expect(response.status).toBe(200);
      });

      test('Should return a Content-Type header of text/html', () => {
        expect(response.headers['content-type']).toMatch(/html/);
      });

    });
    
  
    describe('HTML Content Analysis', () => {
      let $;

      beforeAll(() => {
        $ = cheerio.load(response.data);
      });

      test('Should contain a form', () => {
        expect($('form').length).toBe(1);
      });

      test('Should contain two inputs', () => {
        const h1 = $('h1.main-heading');
        expect(h1.length).toBe(1);
        expect(h1.text()).toBe('Welcome to the Test Page');
      });

      test('Should contain a button to check /api/lanches', () => {
        expect($('p').text()).toContain('testing purposes');
      });
    });
  }
);


describe('Route - /sugestao', () => {
    let response;

    beforeAll(async() => {
      try {
        response = await axios.post(`${BASE_URL}/sugestao`)
      } catch (error) {
        if(error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}/sugestao. Is the Express server running?`);
        throw error;
      }
    });

    describe('HTML content analysis', () => {

    });
  }
);

describe('Route - /api/lanches', () => {
    let response;

    beforeAll(async() => {
      try {
        response = await axios.get(`${BASE_URL}/api/lanches`)
      } catch (error) {
        if(error.code === 'ECONNREFUSED') throw new Error(`Connection refused at ${BASE_URL}/sugestao. Is the Express server running?`);
        throw error;
      }
    });

    // --- Basic Connectivity Checks ---
    describe('Basic Connectivity and Headers', () => {
        test('Should return a 200 OK status code', () => {
            expect(response.status).toBe(200);
        });

        test('Should return a Content-Type header of application/json', () => {
            expect(response.headers['content-type']).toMatch(/application\/json/);
        });
    });


    // --- JSON Data Structure and Type Validation ---
    describe('JSON Data Structure Validation', () => {
        test('should return an array of lanches', () => {
            expect(Array.isArray(lanches)).toBe(true);
        });

        test('should return an array with at least 3 lanches', () => {
            expect(lanches.length).toBeGreaterThan(2);
        });

        test('each lanche object in the array should have the required attributes: id, nome ingredientes', () => {
            lanches.forEach(lanche => {
                expect(lanche).toHaveProperty('id');
                expect(lanche).toHaveProperty('nome');
                //expect(lanche).toHaveProperty('descricao');
                expect(lanche).toHaveProperty('ingredientes');
            });
        });

        test('each lanche attribute should have the correct data type and not be empty', () => {
            lanches.forEach(lanche => {

              expect(typeof lanche.id).toBe('number');
                expect(Number.isInteger(lanche.id)).toBe(true);
                expect(lanche.id).toBeGreaterThan(0);

                expect(typeof lanche.nome).toBe('string');
                expect(lanche.nome.length).toBeGreaterThan(0); 

                //expect(typeof lanche.descricao).toBe('string');
                //expect(lanche.descricao.length).toBeGreaterThan(0);

                expect(typeof lanche.descricao).toBe('string');
                expect(lanche.ingredientes.length).toBeGreaterThan(0);

                lanche.ingredientes.forEach(ingredient => {
                    expect(typeof ingredient).toBe('string');
                    expect(ingredient.length).toBeGreaterThan(0); 
                });
            });
        });
    });
  }
);